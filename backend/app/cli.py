"""Management commands.

  python -m app.cli issue-key --label "Customer ref 123" --expires 2027-12-31
      Prints an ad-free licence key signed with PREMIUM_SECRET (backend/.env).
  python -m app.cli new-secret
      Prints a random value suitable for PREMIUM_SECRET.
"""
import argparse
import secrets
import sys

from .api.reference import sign_key
from .core.config import get_settings


def main(argv=None):
    ap = argparse.ArgumentParser(prog='python -m app.cli')
    sub = ap.add_subparsers(dest='cmd', required=True)
    k = sub.add_parser('issue-key')
    k.add_argument('--label', default='')
    k.add_argument('--expires', default=None, help='YYYY-MM-DD (optional)')
    sub.add_parser('new-secret')
    a = ap.parse_args(argv)
    if a.cmd == 'new-secret':
        print(secrets.token_urlsafe(48))
        return 0
    secret = get_settings().PREMIUM_SECRET
    if not secret:
        print('PREMIUM_SECRET is empty in backend/.env - set it first (python -m app.cli new-secret).')
        return 1
    payload = {'v': 1, 'label': a.label[:80], 'n': secrets.token_hex(4)}
    if a.expires:
        payload['exp'] = a.expires
    print(sign_key(payload, secret))
    return 0


if __name__ == '__main__':
    sys.exit(main())
