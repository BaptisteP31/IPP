import logging
import os
import secrets
import tempfile
import threading
import time
from configparser import ConfigParser

import requests
from flask import Flask, Response, abort, jsonify, request
from webdbf import HEADERS, fetch_ics, normalize_ics
from werkzeug.exceptions import HTTPException, InternalServerError

CONFIG_FILE = 'config.ini'
TOKENS_FILE = 'tokens.ini'
CACHE_DIR = 'cache'
MIN_CACHED_EVENTS = 10
MIN_EVENT_RATIO = 0.5  # A half-failed login can return a nearly empty calendar.
REFRESH_INTERVAL = 3600  # seconds between two fetches of the same calendar

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
log = logging.getLogger('ipp')

def load_config(config_file=CONFIG_FILE):
    """Load and return the configuration."""
    config = ConfigParser()
    config.read(config_file)
    return config


def cache_path(section):
    return os.path.join(CACHE_DIR, f'{section}.ics')


def store_calendar(section, content):
    content = normalize_ics(content)
    if not content.startswith(b'BEGIN:VCALENDAR'):
        raise ValueError('Content is not an ICS calendar.')
    count = content.count(b'BEGIN:VEVENT')
    if not count:
        raise ValueError('Calendar contains no events.')
    try:
        with open(cache_path(section), 'rb') as f:
            old_count = f.read().count(b'BEGIN:VEVENT')
    except FileNotFoundError:
        old_count = 0
    if old_count >= MIN_CACHED_EVENTS and count < old_count * MIN_EVENT_RATIO:
        raise ValueError('Calendar has too few events compared with the cached copy.')
    os.makedirs(CACHE_DIR, exist_ok=True)
    tmp = None
    try:
        with tempfile.NamedTemporaryFile(dir=CACHE_DIR, delete=False) as f:
            tmp = f.name
            f.write(content)
        os.replace(tmp, cache_path(section))
    finally:
        if tmp and os.path.exists(tmp):
            os.unlink(tmp)


def refresh_all(config):
    """Fetch every calendar and replace its cached copy. Keep the old copy on error."""
    os.makedirs(CACHE_DIR, exist_ok=True)
    for section in config.sections():
        mode = config[section].get('MODE', 'pull')
        if mode not in ('pull', 'push'):
            log.error('Invalid MODE for %s: %s', section, mode)
            continue
        if mode == 'push':
            continue
        try:
            content = fetch_ics(config, section)
            store_calendar(section, content)
        except (requests.exceptions.RequestException, ValueError, OSError) as e:
            log.error('Refresh of %s failed, keeping cached copy: %s', section, e)
            continue
        log.info('Refreshed %s (%d bytes)', section, len(content))


def refresh_loop(config):
    while True:
        try:
            refresh_all(config)
        except Exception:
            # Never let the refresh thread die: the app would silently serve stale data forever.
            log.exception('Unexpected error during refresh')
        time.sleep(REFRESH_INTERVAL)


def find_token(token, push=False):
    """Return (name, allowed sections) for a token, or None. Re-read on every call so edits apply live."""
    tokens = ConfigParser()
    tokens.read(TOKENS_FILE)
    for name in tokens.sections():
        stored = tokens[name].get('PUSH_TOKEN' if push else 'TOKEN', '')
        if stored and secrets.compare_digest(stored, token):
            allowed = {s.strip() for s in tokens[name].get('PUSH_SECTIONS' if push else 'SECTIONS', '').split(',') if s.strip()}
            return name, allowed
    return None


def create_app(config):
    app = Flask(__name__)
    app.config['MAX_CONTENT_LENGTH'] = 2 * 1024 * 1024

    @app.errorhandler(HTTPException)
    def http_error(e):
        return jsonify(status=e.code, error=e.name, message=e.description), e.code

    @app.errorhandler(Exception)
    def unexpected_error(e):
        log.exception('Unhandled error')
        return http_error(InternalServerError('Internal server error.'))

    @app.route('/push/<section>', methods=['POST'])
    def push_ics(section):
        parts = request.headers.get('Authorization', '').split()
        match = find_token(parts[1], push=True) if len(parts) == 2 and parts[0].lower() == 'bearer' else None
        if match is None or section not in match[1] or section not in config:
            abort(401, description='Push not authorized.')
        if config[section].get('MODE', 'pull') != 'push':
            abort(409, description='Calendar is not in push mode.')
        content = request.get_data()
        try:
            store_calendar(section, content)
        except ValueError as e:
            abort(400, description=str(e))
        log.info('Pushed %s by %s (%d bytes)', section, match[0], len(content))
        return '', 204

    @app.route('/<token>/<section>')
    def get_ics(token, section):
        # Same response for an unknown token and a forbidden section: never reveal that a token is valid.
        not_found = 'Calendar not found.'
        match = find_token(token)
        if match is None:
            abort(404, description=not_found)
        name, allowed = match
        if section not in allowed or section not in config.sections():
            abort(404, description=not_found)

        try:
            with open(cache_path(section), 'rb') as f:
                content = f.read()
        except FileNotFoundError:
            abort(503, description='Calendar not available yet, retry later.')

        log.info('Served %s to %s', section, name)
        return Response(
            content,
            mimetype='text/calendar',
            headers={'Content-Disposition': f'attachment; filename={section}.ics'}
        )

    return app


config = load_config()
log.info('Loaded configuration sections: %s', config.sections())
threading.Thread(target=refresh_loop, args=(config,), daemon=True).start()
app = create_app(config)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
