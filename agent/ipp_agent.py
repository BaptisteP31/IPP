# /// script
# requires-python = ">=3.11"
# dependencies = ["requests"]
# ///
import argparse
import configparser
import logging
import os
from pathlib import Path
from urllib.parse import quote, urlsplit

import requests

# Mirrors the server's webdbf client.
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:142.0) Gecko/20100101 Firefox/142.0',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'fr,fr-FR;q=0.8,en-US;q=0.5,en;q=0.3',
    'Content-Type': 'application/x-www-form-urlencoded',
    'Origin': 'https://webdfd.mines-ales.fr',
    'Referer': 'https://webdfd.mines-ales.fr/planning-eleves/index.php',
    'Upgrade-Insecure-Requests': '1', 'Sec-Fetch-Dest': 'document',
    'Sec-Fetch-Mode': 'navigate', 'Sec-Fetch-Site': 'same-origin',
    'Sec-Fetch-User': '?1', 'Priority': 'u=0, i',
}
log = logging.getLogger('ipp-agent')


def load_config(path):
    config = configparser.ConfigParser(interpolation=None)
    try:
        with path.open() as f:
            config.read_file(f)
        if path.stat().st_mode & 0o077:
            log.warning('Config is readable or accessible by group/others; use chmod 600')
        sections = [s for s in config.sections() if s != 'ipp']
        if not sections or not config.has_section('ipp'):
            raise ValueError('an [ipp] section and at least one calendar are required')
        for key in ('SERVER', 'PUSH_TOKEN'):
            if not config['ipp'][key].strip():
                raise ValueError(f'missing {key}')
        server = urlsplit(config['ipp']['SERVER'])
        if not server.hostname or (server.scheme != 'https' and not (server.scheme == 'http' and server.hostname in ('localhost', '127.0.0.1', '::1'))):
            raise ValueError('SERVER must use HTTPS')
        for section in sections:
            for key in ('LOGIN_URL', 'URL', 'USERNAME', 'PASSWORD'):
                if not config[section][key].strip():
                    raise ValueError(f'missing {key} in {section}')
            for key in ('LOGIN_URL', 'URL'):
                url = urlsplit(config[section][key])
                if url.scheme not in ('http', 'https') or not url.hostname:
                    raise ValueError(f'invalid {key} in {section}')
        return config, sections
    except (OSError, configparser.Error, KeyError, ValueError) as exc:
        raise ValueError(f'invalid or missing configuration: {exc}') from exc


class StepError(Exception):
    def __init__(self, step, error):
        self.step = step
        self.error = error


def request_step(step, operation):
    try:
        return operation()
    except requests.RequestException as exc:
        raise StepError(step, exc) from exc


def checked_response(operation):
    response = operation()
    response.raise_for_status()
    return response


def fetch(calendar):
    with requests.Session() as session:
        response = request_step('login', lambda: checked_response(lambda: session.post(calendar['LOGIN_URL'], headers=HEADERS, data={
            'Username': calendar['USERNAME'], 'Password': calendar['PASSWORD'],
            'url': '', 'login': ''}, timeout=30)))
        response = request_step('download', lambda: checked_response(
            lambda: session.get(calendar['URL'], headers=HEADERS, timeout=30)))
        if not response.content.lstrip().startswith(b'BEGIN:VCALENDAR'):
            raise ValueError('login failed or response is not a calendar')
        return response.content


def push(config, section, content):
    response = requests.post(config['SERVER'].rstrip('/') + '/push/' + quote(section, safe=''),
                             headers={'Authorization': 'Bearer ' + config['PUSH_TOKEN'],
                                      'Content-Type': 'text/calendar'}, data=content, timeout=30)
    if response.status_code == 204:
        return
    messages = {400: 'calendar rejected', 401: 'bad token or section not allowed',
                409: 'section is not in push mode', 413: 'calendar too large'}
    message = messages.get(response.status_code, 'server error')
    if response.status_code == 400:
        try:
            detail = response.json().get('message')
            if isinstance(detail, str):
                message += ': ' + detail.replace(config['PUSH_TOKEN'], '[redacted]')
        except (ValueError, AttributeError):
            pass
    raise ValueError(f'HTTP {response.status_code}: {message}')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--config', type=Path, default=Path('~/.config/ipp-agent/config.ini').expanduser())
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('-v', action='store_true')
    args = parser.parse_args()
    logging.basicConfig(level=logging.DEBUG if args.v else logging.INFO, format='%(message)s')
    # requests debug logs can contain URLs or credentials.
    logging.getLogger('urllib3').setLevel(logging.WARNING)
    try:
        config, sections = load_config(args.config.expanduser())
    except ValueError as exc:
        log.error('%s', exc)
        return 2
    reachable = {}
    failed = False
    for section in sections:
        url = urlsplit(config[section]['LOGIN_URL'])
        host = (url.scheme, url.hostname, url.port)
        if host not in reachable:
            try:
                response = requests.get(f'{url.scheme}://{url.netloc}/', timeout=5)
                # A 403 at the host root is assumed to mean access is restricted to school.
                reachable[host] = response.status_code != 403
                if not reachable[host]:
                    log.info('school network probe returned HTTP 403')
            except (requests.ConnectionError, requests.Timeout):
                reachable[host] = False
            except requests.RequestException:
                log.error('%s: school network check failed', section)
                reachable[host] = False
                failed = True
        if not reachable[host]:
            log.info('%s: school host not reachable, skipping', section)
            continue
        try:
            content = fetch(config[section])
            if not args.dry_run:
                request_step('push', lambda: push(config['ipp'], section, content))
            log.info('%s: %s', section, 'validated (dry run)' if args.dry_run else 'pushed')
        except StepError as exc:
            error = exc.error
            if isinstance(error, requests.HTTPError) and error.response is not None:
                detail = f'HTTP {error.response.status_code}'
            elif isinstance(error, requests.Timeout):
                detail = 'timeout'
            elif isinstance(error, requests.ConnectionError):
                detail = 'connection error'
            else:
                detail = 'request error'
            log.error('%s: %s failed (%s)', section, exc.step, detail)
            failed = True
        except ValueError as exc:
            # Request exceptions can include URLs containing sensitive values.
            message = str(exc)
            for secret in (config['ipp']['PUSH_TOKEN'], config[section]['PASSWORD']):
                message = message.replace(secret, '[redacted]')
            log.error('%s: %s', section, message)
            failed = True
    return int(failed)


if __name__ == '__main__':
    raise SystemExit(main())
