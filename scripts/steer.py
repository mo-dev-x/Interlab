#!/usr/bin/env python
"""Thin CLI wrapper: arg-parse -> interplab.jobs.steer (§1)."""

import argparse
import sys

from interplab.jobs import steer


def main() -> int:
    parser = argparse.ArgumentParser(description="Run SS7/SS8 steering generation (GATE G3 consumer) against a config.")
    parser.add_argument("--config", required=True, help="Path to a steer_v1-schema config YAML.")
    args = parser.parse_args()
    return steer.run(args.config)


if __name__ == "__main__":
    sys.exit(main())
