

import argparse
import os
from . import __version__ as version


def make_parser():
    parser = argparse.ArgumentParser()
    parser.add_argument('--version', '-v', action='version', version=version)
    return parser

def main():
    args = make_parser().parse_args()

    print(f'Visit <https://{os.getenv("DOMAIN_NAME")}>')

