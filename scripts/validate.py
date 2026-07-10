#!/usr/bin/env python
"""Thin CLI wrapper: arg-parse -> interplab.jobs.validate (§1)."""

import argparse
import sys

from interplab.jobs import validate


def main() -> int:
    parser = argparse.ArgumentParser(description="Run SS6 validation (GATE G2) against a config.")
    parser.add_argument("--config", required=True, help="Path to a validate_v1-schema config YAML.")
    args = parser.parse_args()
    return validate.run(args.config)


if __name__ == "__main__":
    sys.exit(main())
