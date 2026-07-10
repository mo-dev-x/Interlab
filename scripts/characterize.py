#!/usr/bin/env python
"""Thin CLI wrapper: arg-parse -> interplab.jobs.characterize (§1)."""

import argparse
import sys

from interplab.jobs import characterize


def main() -> int:
    parser = argparse.ArgumentParser(description="Run SS5 characterization against a config.")
    parser.add_argument("--config", required=True, help="Path to a characterize_v1-schema config YAML.")
    args = parser.parse_args()
    return characterize.run(args.config)


if __name__ == "__main__":
    sys.exit(main())
