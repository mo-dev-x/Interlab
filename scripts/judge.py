#!/usr/bin/env python
"""Thin CLI wrapper: arg-parse -> interplab.jobs.judge (§1)."""

import argparse
import sys

from interplab.jobs import judge


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run SS8 judging/capability ingestion against one unjudged intervention_result config."
    )
    parser.add_argument("--config", required=True, help="Path to a judge_v1-schema config YAML.")
    args = parser.parse_args()
    return judge.run(args.config)


if __name__ == "__main__":
    sys.exit(main())
