#!/usr/bin/env python3
import sys

from ptcg_meta_bench.cli import main


if __name__ == "__main__":
    raise SystemExit(main(["quickstart", *sys.argv[1:]]))
