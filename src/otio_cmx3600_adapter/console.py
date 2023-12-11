import argparse

from .edl_parser import statements_from_string


def edldump():
    parser = argparse.ArgumentParser(
        prog="edldump",
        description="Dumps parsed EDL statements",
    )
    parser.add_argument("filename")
    args = parser.parse_args()
    with open(args.filename) as infile:
        for statement in statements_from_string(infile.read()):
            print(statement)

    return 0
