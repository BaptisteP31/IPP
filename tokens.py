"""Manage access tokens stored in tokens.ini.

Usage:
    python tokens.py add <name> <section> [<section> ...]
    python tokens.py push-add <name> <section> [<section> ...]
    python tokens.py push-revoke <name>
    python tokens.py revoke <name>
    python tokens.py list
"""
import secrets
import sys
from configparser import ConfigParser

TOKENS_FILE = 'tokens.ini'
CONFIG_FILE = 'config.ini'


def load(path):
    parser = ConfigParser()
    parser.read(path)
    return parser


def save(tokens):
    with open(TOKENS_FILE, 'w') as f:
        tokens.write(f)


def add(name, sections):
    known = load(CONFIG_FILE).sections()
    unknown = [s for s in sections if s not in known]
    if unknown:
        sys.exit(f"Unknown section(s): {', '.join(unknown)}. Available: {', '.join(known)}")

    tokens = load(TOKENS_FILE)
    if tokens.has_section(name) and tokens[name].get('TOKEN'):
        sys.exit(f"'{name}' already has a token. Revoke it first.")
    if not tokens.has_section(name):
        tokens.add_section(name)

    token = secrets.token_urlsafe(24)
    tokens[name]['TOKEN'] = token
    tokens[name]['SECTIONS'] = ', '.join(sections)
    save(tokens)
    for section in sections:
        print(f'/{token}/{section}')


def push_add(name, sections):
    config = load(CONFIG_FILE)
    invalid = [s for s in sections if s not in config or config[s].get('MODE', 'pull') != 'push']
    if invalid:
        sys.exit(f"Unknown or non-push section(s): {', '.join(invalid)}")
    tokens = load(TOKENS_FILE)
    if not tokens.has_section(name):
        tokens.add_section(name)
    if tokens[name].get('PUSH_TOKEN'):
        sys.exit(f"'{name}' already has a push token. Revoke it first.")
    token = secrets.token_urlsafe(32)
    tokens[name]['PUSH_TOKEN'] = token
    tokens[name]['PUSH_SECTIONS'] = ', '.join(sections)
    save(tokens)
    print(token)
    for section in sections:
        print(f'/push/{section}')


def push_revoke(name):
    tokens = load(TOKENS_FILE)
    if not tokens.has_section(name) or not tokens[name].get('PUSH_TOKEN'):
        sys.exit(f"No push token for '{name}'.")
    tokens.remove_option(name, 'PUSH_TOKEN')
    tokens.remove_option(name, 'PUSH_SECTIONS')
    if not tokens.items(name):
        tokens.remove_section(name)
    save(tokens)
    print(f"Revoked push token of '{name}'.")


def revoke(name):
    tokens = load(TOKENS_FILE)
    if not tokens.remove_section(name):
        sys.exit(f"No token for '{name}'.")
    save(tokens)
    print(f"Revoked token of '{name}'.")


def list_tokens():
    tokens = load(TOKENS_FILE)
    for name in tokens.sections():
        print(f"{name}: read: {tokens[name].get('SECTIONS', '')}; push: {tokens[name].get('PUSH_SECTIONS', '')}")


if __name__ == '__main__':
    args = sys.argv[1:]
    if len(args) >= 3 and args[0] == 'add':
        add(args[1], args[2:])
    elif len(args) >= 3 and args[0] == 'push-add':
        push_add(args[1], args[2:])
    elif len(args) == 2 and args[0] == 'push-revoke':
        push_revoke(args[1])
    elif len(args) == 2 and args[0] == 'revoke':
        revoke(args[1])
    elif args == ['list']:
        list_tokens()
    else:
        sys.exit(__doc__)
