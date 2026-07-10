#!/usr/bin/env python
"""Thin CLI wrapper: arg-parse -> interplab.jobs.backfill_checkpoint (ED-5)."""

import argparse
import sys

from interplab.jobs import backfill_checkpoint


def main() -> int:
    parser = argparse.ArgumentParser(description="Register a backfilled A5 manifest for a legacy checkpoint.")
    parser.add_argument("--config", required=True, help="Path to a backfill_checkpoint_v1-schema config YAML.")
    args = parser.parse_args()
    return backfill_checkpoint.run(args.config)


if __name__ == "__main__":
    sys.exit(main())
