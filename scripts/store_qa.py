#!/usr/bin/env python
"""Thin CLI wrapper: arg-parse -> interplab.jobs.store_qa (§1)."""

import argparse
import sys

from interplab.jobs import store_qa


def main() -> int:
    parser = argparse.ArgumentParser(description="Run SS2 store QA against a config.")
    parser.add_argument("--config", required=True, help="Path to a store_qa_v1-schema config YAML.")
    args = parser.parse_args()
    return store_qa.run(args.config)


if __name__ == "__main__":
    sys.exit(main())
