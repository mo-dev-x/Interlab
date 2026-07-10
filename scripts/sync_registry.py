#!/usr/bin/env python
"""Thin CLI wrapper: arg-parse -> interplab.jobs.sync_registry (§1)."""

import argparse
import sys

from interplab.jobs import sync_registry


def main() -> int:
    parser = argparse.ArgumentParser(description="Pull cluster-outbox artifacts into registry/ (§3.3).")
    parser.add_argument("--config", required=True, help="Path to a sync_registry_v1-schema config YAML.")
    args = parser.parse_args()
    return sync_registry.run(args.config)


if __name__ == "__main__":
    sys.exit(main())
