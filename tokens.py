"""Manage access tokens stored in tokens.ini.

Usage:
    python tokens.py add <name> <section> [<section> ...]
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
    if tokens.has_section(name):
        sys.exit(f"'{name}' already has a token. Revoke it first.")

    token = secrets.token_urlsafe(24)
    tokens[name] = {'TOKEN': token, 'SECTIONS': ', '.join(sections)}
    save(tokens)
    for section in sections:
        print(f'/{token}/{section}')


def revoke(name):
    tokens = load(TOKENS_FILE)
    if not tokens.remove_section(name):
        sys.exit(f"No token for '{name}'.")
    save(tokens)
    print(f"Revoked token of '{name}'.")


def list_tokens():
    tokens = load(TOKENS_FILE)
    for name in tokens.sections():
        print(f"{name}: {tokens[name].get('SECTIONS', '')}")


if __name__ == '__main__':
    args = sys.argv[1:]
    if len(args) >= 3 and args[0] == 'add':
        add(args[1], args[2:])
    elif len(args) == 2 and args[0] == 'revoke':
        revoke(args[1])
    elif args == ['list']:
        list_tokens()
    else:
        sys.exit(__doc__)
