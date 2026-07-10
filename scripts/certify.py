#!/usr/bin/env python
"""Thin CLI wrapper: arg-parse -> interplab.jobs.certify (§1)."""

import argparse
import sys

from interplab.jobs import certify


def main() -> int:
    parser = argparse.ArgumentParser(description="Run SS4 certification (GATE G1) against a config.")
    parser.add_argument("--config", required=True, help="Path to a certify_v1-schema config YAML.")
    args = parser.parse_args()
    return certify.run(args.config)


if __name__ == "__main__":
    sys.exit(main())
