"""One-time extraction script (ED-8): mechanically migrates the ConceptBattery
source material out of `scripts/find_features.py`'s `PROBES`/`GENERAL_TEXT`/
`GENERAL_TEXT_ZH` constants into `data/concepts/*.yaml`.

This is NOT re-run by any job or test -- kept committed for provenance only,
exactly like `tests/fixtures/generate.py` (§8.1). It performs no scientific
authorship: every probe and every negative-control sentence it writes is
copied verbatim from the existing source constants. It does not translate,
does not invent negative controls for languages that lack them, and does not
invent `matched_controls` relationships the source data does not contain.

ED-10 (supersedes the ED-8-era word_absent handling below): GENERAL_TEXT /
GENERAL_TEXT_ZH are `concept_absent` (unrelated baseline text, the
specificity-denominator instrument), NOT `word_absent` (concept-present,
term-absent contexts, the sensitivity instrument -- a different scientific
instrument entirely; conflating them inverts the sensitivity measurement).
The source corpus contains no true word-absent contexts for any language.
`en`/`zh` get `concept_absent` from GENERAL_TEXT/GENERAL_TEXT_ZH;
`word_absent` is `[]` for every language in battery v1. Since `status`
(ED-8) is governed by `word_absent` alone, every language is `probes_only`
in battery v1 -- existing probes are never discarded for lacking a negative
control (ED-8), and SS6 sensitivity remains unimplementable until the
researcher authors real word-absent content (battery v2+).

ED-9: census_terms are battery content -- researcher-authored, same policy
as ED-8 -- with one mechanical carve-out: the English term MAY be derived
from concept_id (word-separator -> space), origin: "concept_id", since the
identifier itself originates from source, not from any act of translation.
This script does NOT mine `find_features.py`'s legacy behavioral keyword
lists (e.g. POUTINE_KEYWORDS) for census terms -- ED-9 explicitly prohibits
that (those lists encode associative matching, a different instrument) --
and does NOT author non-English census terms. fr/zh/ar therefore get
census_terms: [] in battery v1 (status "no_terms" for census, independent
of their probes_only/complete sensitivity status).
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
CONCEPTS_DIR = Path(__file__).resolve().parent

sys.path.insert(0, str(REPO_ROOT / "scripts"))
import find_features as ff  # noqa: E402

SOURCE_FILE = "scripts/find_features.py"
CONCEPT_ABSENT_BY_LANG = {"en": list(ff.GENERAL_TEXT), "zh": list(ff.GENERAL_TEXT_ZH)}


def _source_commit() -> str:
    return subprocess.check_output(
        ["git", "log", "-1", "--format=%H", "--", SOURCE_FILE], cwd=REPO_ROOT, text=True
    ).strip()


class _Dumper(yaml.SafeDumper):
    pass


_Dumper.add_representer(
    str,
    lambda dumper, data: dumper.represent_scalar(
        "tag:yaml.org,2002:str", data, style="|" if "\n" in data else None
    ),
)


def _english_census_term(concept_id: str) -> str:
    """ED-9: mechanical derivation only -- concept_id's word separators
    (source uses "_", the battery's kebab-case field uses "-") become
    spaces. No translation, no keyword extraction, no morphology."""
    return concept_id.replace("_", " ").replace("-", " ")


def build_concepts(commit: str) -> dict[str, dict]:
    concepts: dict[str, dict] = {}
    for concept_id, lang_probes in ff.PROBES.items():
        kebab_id = concept_id.replace("_", "-")
        languages = {}
        for lang, probes in lang_probes.items():
            concept_absent = CONCEPT_ABSENT_BY_LANG.get(lang, [])
            word_absent: list[str] = []  # ED-10: source has no true word-absent contexts
            status = "complete" if len(word_absent) >= 5 else "probes_only"
            if lang == "en":
                census_terms = [
                    {"term": _english_census_term(concept_id), "kind": "canonical", "origin": "concept_id"}
                ]
            else:
                census_terms = []
            languages[lang] = {
                "status": status,
                "probes": list(probes),
                "word_absent": word_absent,
                "concept_absent": concept_absent,
                "census_terms": census_terms,
            }
        notes = (
            f"Extracted verbatim from {SOURCE_FILE} (commit {commit}), "
            f"PROBES[{concept_id!r}]. "
            + (
                "concept_absent for en/zh copied from the same file's "
                "GENERAL_TEXT/GENERAL_TEXT_ZH (the pre-existing general-text "
                "specificity baseline). word_absent is empty for every "
                "language: the source contains no concept-present, "
                "term-absent contexts (ED-10) -- all languages are "
                "probes_only in battery v1. census_terms (ED-9): en derived "
                "mechanically from concept_id (origin: concept_id); "
                "fr/zh/ar left empty (status no_terms for census) pending "
                "researcher authorship -- legacy behavioral keyword lists "
                "were not mined for this."
            )
        )
        concepts[concept_id] = {
            "concept_id": kebab_id,
            "languages": languages,
            "matched_controls": [],
            "notes": notes,
        }
    return concepts


def main() -> None:
    commit = _source_commit()
    concepts = build_concepts(commit)

    for payload in concepts.values():
        out_path = CONCEPTS_DIR / f"{payload['concept_id']}.yaml"
        with open(out_path, "w", encoding="utf-8") as f:
            yaml.dump(payload, f, Dumper=_Dumper, allow_unicode=True, sort_keys=False, width=100)
        print(f"wrote {out_path.relative_to(REPO_ROOT)}")

    battery = {
        "battery_version": "1.0.0",
        "provenance": {
            "extracted_from": SOURCE_FILE,
            "commit": commit,
            "extraction_script": "data/concepts/extract_from_find_features.py",
        },
    }
    battery_path = CONCEPTS_DIR / "battery.yaml"
    with open(battery_path, "w", encoding="utf-8") as f:
        yaml.dump(battery, f, sort_keys=False)
    print(f"wrote {battery_path.relative_to(REPO_ROOT)}")


if __name__ == "__main__":
    main()
