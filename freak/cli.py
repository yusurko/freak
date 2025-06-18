

import argparse
import os
import subprocess

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from . import __version__ as version, app
from .models import User, db

def make_parser():
    parser = argparse.ArgumentParser()
    parser.add_argument('--version', '-v', action='version', version=version)
    parser.add_argument('--upgrade', '-U', action='store_true', help='create or upgrade schema')
    parser.add_argument('--flush',   '-H', action='store_true', help='recompute karma for all users')
    return parser

def main():
    args = make_parser().parse_args()

    engine = create_engine(os.getenv('DATABASE_URL'))
    if args.upgrade:
        ret_code = subprocess.Popen(['alembic', 'upgrade', 'head']).wait()
        if ret_code != 0:
            print(f'Schema upgrade failed (code: {ret_code})')
            exit(ret_code)
        # if the alembic/versions folder is empty
        db.metadata.create_all(engine)
        print('Schema upgraded!')

    if args.flush:
        cnt = 0
        with app.app_context():
            for u in db.session.execute(select(User)).scalars():
                u.recompute_karma()
                cnt += 1
                db.session.add(u)
            db.session.commit()
        print(f'Recomputed karma of {cnt} users')

    print(f'Visit <https://{os.getenv("DOMAIN_NAME")}>')

