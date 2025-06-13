

import argparse
import os
import subprocess
from . import __version__ as version
from .models import db

def make_parser():
    parser = argparse.ArgumentParser()
    parser.add_argument('--version', '-v', action='version', version=version)
    parser.add_argument('--upgrade', '-U', action='store_true', help='create or upgrade schema')
    return parser

def main():
    args = make_parser().parse_args()
    if args.upgrade:
        db.metadata.create_all()
        subprocess.Popen(['alembic', 'upgrade', 'head']).wait()
        print('Schema upgraded!')

    print(f'Visit <https://{os.getenv("DOMAIN_NAME")}>')

