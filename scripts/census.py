#!/usr/bin/env python
"""Thin CLI wrapper: arg-parse -> interplab.jobs.census (§1)."""

import argparse
import sys

from interplab.jobs import census


def main() -> int:
    parser = argparse.ArgumentParser(description="Run SS1 census against a config.")
    parser.add_argument("--config", required=True, help="Path to a census_v1-schema config YAML.")
    args = parser.parse_args()
    return census.run(args.config)


if __name__ == "__main__":
    sys.exit(main())
