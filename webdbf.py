import requests

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

    return normalize_ics(ics_response.content)


def normalize_ics(raw):
    """Return the ICS as UTF-8 with CRLF line endings, as RFC 5545 requires.

    webdbf sends Latin-1 while declaring charset=utf-8, so accents break in every client.
    It also mixes LF and CRLF line endings.
    """
    try:
        text = raw.decode('utf-8')  # In case webdbf fixes its encoding one day.
    except UnicodeDecodeError:
        text = raw.decode('cp1252', errors='replace')  # Superset of Latin-1 (adds ’, €, œ...).
    text = text.lstrip('\ufeff \t\r\n\v\f')
    text = text.replace('\r\n', '\n').replace('\n', '\r\n')
    return text.encode('utf-8')
