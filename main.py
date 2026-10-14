import logging
import os
import secrets
import threading
import time
from configparser import ConfigParser

import requests
from flask import Flask, Response, abort, jsonify
from werkzeug.exceptions import HTTPException, InternalServerError

CONFIG_FILE = 'config.ini'
TOKENS_FILE = 'tokens.ini'
CACHE_DIR = 'cache'
REFRESH_INTERVAL = 3600  # seconds between two fetches of the same calendar

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
log = logging.getLogger('ipp')

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:142.0) Gecko/20100101 Firefox/142.0',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'fr,fr-FR;q=0.8,en-US;q=0.5,en;q=0.3',
    'Content-Type': 'application/x-www-form-urlencoded',
    'Origin': 'https://webdfd.mines-ales.fr',
    'Referer': 'https://webdfd.mines-ales.fr/planning-eleves/index.php',
    'Upgrade-Insecure-Requests': '1',
    'Sec-Fetch-Dest': 'document',
    'Sec-Fetch-Mode': 'navigate',
    'Sec-Fetch-Site': 'same-origin',
    'Sec-Fetch-User': '?1',
    'Priority': 'u=0, i'
}


def load_config(config_file=CONFIG_FILE):
    """Load and return the configuration."""
    config = ConfigParser()
    config.read(config_file)
    return config


def cache_path(section):
    return os.path.join(CACHE_DIR, f'{section}.ics')


def fetch_ics(config, section):
    """Log in to webdbf and return the ICS content for the given section."""
    form_data = {
        'Username': config[section]['USERNAME'],
        'Password': config[section]['PASSWORD'],
        'url': '',
        'login': ''
    }

    session = requests.Session()
    login_response = session.post(config[section]['LOGIN_URL'], headers=HEADERS, data=form_data, timeout=30)
    login_response.raise_for_status()

    ics_response = session.get(config[section]['URL'], headers=HEADERS, timeout=30)
    ics_response.raise_for_status()

    # A failed login usually comes back as an HTML page with a 200 status.
    if not ics_response.content.lstrip().startswith(b'BEGIN:VCALENDAR'):
        raise ValueError('response is not an ICS file (login failed?)')

    return ics_response.content


def refresh_all(config):
    """Fetch every calendar and replace its cached copy. Keep the old copy on error."""
    os.makedirs(CACHE_DIR, exist_ok=True)
    for section in config.sections():
        try:
            content = fetch_ics(config, section)
            tmp = cache_path(section) + '.tmp'
            with open(tmp, 'wb') as f:
                f.write(content)
            os.replace(tmp, cache_path(section))
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


def find_token(token):
    """Return (name, allowed sections) for a token, or None. Re-read on every call so edits apply live."""
    tokens = ConfigParser()
    tokens.read(TOKENS_FILE)
    for name in tokens.sections():
        stored = tokens[name].get('TOKEN', '')
        if stored and secrets.compare_digest(stored, token):
            allowed = {s.strip() for s in tokens[name].get('SECTIONS', '').split(',') if s.strip()}
            return name, allowed
    return None


def create_app(config):
    app = Flask(__name__)

    @app.errorhandler(HTTPException)
    def http_error(e):
        return jsonify(status=e.code, error=e.name, message=e.description), e.code

    @app.errorhandler(Exception)
    def unexpected_error(e):
        log.exception('Unhandled error')
        return http_error(InternalServerError('Internal server error.'))

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
