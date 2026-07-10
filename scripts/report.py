#!/usr/bin/env python
"""Thin CLI wrapper: arg-parse -> interplab.jobs.report (§1)."""

import argparse
import sys

from interplab.jobs import report


def main() -> int:
    parser = argparse.ArgumentParser(description="Assemble a claim chain (SS9, GATE G4) from a claim-spec config.")
    parser.add_argument("--config", required=True, help="Path to a report_v1-schema claim-spec config YAML.")
    args = parser.parse_args()
    return report.run(args.config)


if __name__ == "__main__":
    sys.exit(main())
