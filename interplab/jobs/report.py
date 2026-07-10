"""interplab.jobs.report (SS9, GATE G4 assembly) -- assembles a claim's
certificate chain, composes statistics from anchor payloads only, renders
md/html, stamps CERTIFIED or DRAFT, and writes A11.

Reads the claim spec (job config, §7.2: the YAML *is* the claim spec) +
registry; writes A11 directly to `registry/` (§7.1, same pattern as every
other job in this environment) plus the rendered report under repo-root
`reports/<run_id>/` (ED-17: small files, git-tracked, committed manually).
"""

from __future__ import annotations

from pathlib import Path

from interplab.core import configs, envelope, hashing, uris
from interplab.core.errors import ContractViolationError
from interplab.registry.registry import REGISTRY_ROOT, REPO_ROOT
from interplab.registry.registry import put as registry_put
from interplab.registry.run_card import new_run_card
from interplab.reports import chain as chain_mod
from interplab.reports import render as render_mod
from interplab.reports import statistics as statistics_mod


def run(
    config_path: str | Path,
    *,
    registry_root: Path = REGISTRY_ROOT,
    repo_root: Path = REPO_ROOT,
) -> int:
    claim_spec = configs.load_and_validate(config_path, "report")

    anchor_type = claim_spec["anchor"]["artifact_type"]
    anchor_refs = [
        {
            "content_hash": h,
            "location": f"local:registry/{anchor_type}/{hashing.short_hash(h)}.json",
            "role": anchor_type,
        }
        for h in claim_spec["anchor"]["content_hashes"]
    ]

    handle = new_run_card(
        "report", config_path, registry_root=registry_root, repo_root=repo_root, inputs=anchor_refs,
    )

    status, exit_code, outcome_line = "failed", 4, "unhandled error"
    outputs: list[dict] = []

    try:
        resolution = chain_mod.assemble_chain(claim_spec, registry_root=registry_root)
        statistics, effect_sizes = statistics_mod.compose_statistics(resolution.anchor_artifacts)

        markdown_text = render_mod.render_markdown(
            question=claim_spec["question"], stamp=resolution.stamp, rows=resolution.rows,
            statistics=statistics, effect_sizes=effect_sizes,
        )
        html_text = render_mod.render_html(markdown_text, stamp=resolution.stamp)

        # local: URIs always resolve against the REAL repo root (uris.REPO_ROOT),
        # never the job's own (possibly test-injected) repo_root -- the same
        # rule every prior job applies to registry/results scratch dirs.
        report_dir = uris.REPO_ROOT / "reports" / handle.run_id
        report_dir.mkdir(parents=True, exist_ok=True)
        md_path = report_dir / "report.md"
        html_path = report_dir / "report.html"
        md_path.write_text(markdown_text, encoding="utf-8")
        html_path.write_text(html_text, encoding="utf-8")

        rendered = {
            "md_ref": {
                "content_hash": hashing.hash_file(md_path),
                "location": f"local:{md_path.relative_to(uris.REPO_ROOT).as_posix()}",
            },
            "html_ref": {
                "content_hash": hashing.hash_file(html_path),
                "location": f"local:{html_path.relative_to(uris.REPO_ROOT).as_posix()}",
            },
        }

        payload = {
            "claim_spec": claim_spec,
            "chain": [
                {"link": row.link, "artifact_hash": row.artifact_hash, "status": row.status, "note": row.note}
                for row in resolution.rows
            ],
            "stamp": resolution.stamp,
            "statistics": statistics,
            "figures": [],
            "rendered": rendered,
        }

        subject = [
            {"content_hash": a["self_hash"], "location": ref["location"], "role": anchor_type}
            for a, ref in zip(resolution.anchor_artifacts, anchor_refs, strict=True)
            if a is not None
        ]

        artifact = envelope.dump(
            artifact_type="claim_report",
            schema_version=1,
            created_by=handle.created_by,
            subject=subject,
            payload=payload,
        )
        claim_hash = registry_put(artifact, registry_root=registry_root)

        outputs = [
            {
                "content_hash": claim_hash,
                "location": f"local:registry/claim_report/{hashing.short_hash(claim_hash)}.json",
                "role": "claim_report",
            }
        ]
        # §7.2 point 3: a DRAFT stamp is not an error -- exit 0 either way.
        status, exit_code = "completed", 0
        outcome_line = f"{resolution.stamp} claim_report {hashing.short_hash(claim_hash)}"

    except ContractViolationError as e:
        status, exit_code = "failed", 3
        outcome_line = str(e)
    except Exception as e:  # deliberate catch-all mapping to exit 4 (§6.2)
        status, exit_code = "failed", 4
        outcome_line = f"unexpected error: {e}"
    finally:
        handle.finalize(status, outputs, exit_code, outcome_line=outcome_line)

    return exit_code
