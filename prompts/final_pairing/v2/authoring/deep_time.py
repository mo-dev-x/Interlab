# -*- coding: utf-8 -*-
"""Deep-time vocabulary lexicon, and the F2 invariant that depends on it.

WHY THIS MODULE EXISTS
----------------------
The architect measured the 4edeca4 bytes and found a label-correlated lexical
asymmetry: pro_chinese positives carry deep-time vocabulary, pro_american
positives carry almost none, and eliciting / neutral / unrelated carry none on
either side.

That is dangerous for a reason that is the EXACT MIRROR of RULING_9. RULING_9
proved that form SHARED with the mirror is capped at 0.75 separation and
cannot pass G-A. Deep-time vocabulary runs the same identity the other way:

  For the concept pro_chinese_exceptionalism --
    near_miss   IS pro_american's positives, byte-identical -> ~no deep-time
    unrelated   carries no national referent at all          -> ~no deep-time
  so BOTH halves of G-A's pooled negative set are clean, and a PURE ERA
  DETECTOR scores ~1.0 against both. separation_auroc ~= 1.0. It sails through
  G-A while being no kind of persona feature.

  For the concept pro_american_exceptionalism the same feature runs backwards
  -- its near_miss IS the Chinese positives, which are where the deep-time
  vocabulary lives -- so it scores ~0 and is rejected directionally. THE
  HAZARD IS ONE-SIDED and it points at pro_chinese_exceptionalism.

The byte-identical near-miss design -- this corpus's best defence against
authoring asymmetry -- converts ANY label-correlated lexical asymmetry into a
maximally advantaged discriminator. That is the cost of its greatest strength.

THE PROTECTION, AND WHY IT IS NOW GUARDED RATHER THAN ASSUMED
-------------------------------------------------------------
Gates are evaluated PER PARAPHRASE FAMILY and survival requires all six cells
(3 families x 2 locales). F2 carries NO deep-time vocabulary in either locale,
so a pure era feature sits at ~0.5 in the f2 cells and the family conjunction
kills it. That protection is real and it is currently free.

IT WAS AN ACCIDENT. Nothing measured it, nothing named it, and a single era
phrase entering one f2 row destroys it. Four rewrites landed in F2 -- F2.02
and F2.03, both locales -- and one of them (mine, at 18c4264) did briefly
introduce "long ago" / "depuis longtemps" before it was rolled back at
98b8a21. That is how narrow the margin is.

check_f2_carries_no_deep_time in validate_prompt_sets.py now FAILS on any
deep-time token in any f2 row, in either locale, ON EITHER SIDE -- the
protection requires the family to carry none on both sides, not merely to be
balanced.

WHAT THIS MODULE DOES NOT DO
----------------------------
It does NOT touch f1 or f3. Deep-time content is PERMITTED under RULING_1: it
is asserted, not hedged. What was missing was pre-registration, not
permission, and crossing the factor was expressly NOT ordered. The existing
f1 and f3 rows stand and this module makes no claim about them beyond
counting them for the record.

LEXICON SCOPE, STATED BECAUSE IT DRIVES THE NUMBER
--------------------------------------------------
Markers of GREAT HISTORICAL DEPTH only. Generic temporal vocabulary is
deliberately EXCLUDED -- "generation", "years", "still", "encore", "old
people", "les anciens" (elders) -- because every row of a corpus about
national endurance carries temporal language, and counting it would make the
measure meaningless. The architect's own f2=ZERO result implies the same
exclusions: F2.01 and F2.02 use "generation" and "old people" / "les anciens"
and were counted as zero.

This list is deliberately a SUPERSET of the architect's: it reproduces
f2 == 0 while counting MORE than they did (29 tokens / 19 rows on the Chinese
side against their 19 / 17), so the f2 result is robust to lexicon choice
rather than an artifact of a narrow list.
"""

import hashlib
import json
import re
import unicodedata

WORDS = {
    "en": [
        "ancient", "antiquity", "immemorial", "millennium", "millennia",
        "century", "centuries", "dynasty", "dynasties", "epoch", "epochs",
        "era", "eras", "aeon", "aeons", "primordial", "oldest",
        "bc", "bce", "ad", "ce", "medieval", "prehistoric",
    ],
    "fr": [
        "antiquite", "immemorial", "immemoriale", "millenaire", "millenaires",
        "siecle", "siecles", "dynastie", "dynasties", "epoque", "epoques",
        "ere", "seculaire", "ancestral", "ancestrale", "aieux",
        "medieval", "prehistorique",
    ],
}

PHRASES = {
    "en": [
        "long ago", "far back", "thousand years", "thousands of years",
        "hundreds of years", "age-old", "older than", "since antiquity",
        "time immemorial", "three thousand", "two and a half thousand",
    ],
    "fr": [
        "depuis longtemps", "il y a longtemps", "avant notre ere", "mille ans",
        "des siecles", "trois mille", "deux mille cinq cents",
    ],
}


def _strip(text):
    return "".join(
        ch for ch in unicodedata.normalize("NFD", text)
        if unicodedata.category(ch) != "Mn"
    )


def deep_time_hits(text, locale):
    """Return the deep-time markers present in one row."""
    flat = _strip(text).lower()
    found = []
    for token in WORDS[locale]:
        if re.search(r"(?<![a-z])%s(?![a-z])" % re.escape(token), flat):
            found.append(token)
    for phrase in PHRASES[locale]:
        if phrase in flat:
            found.append(phrase)
    return found


def digest():
    """Hash-pin the lexicon, same discipline as the closed-class instrument."""
    payload = json.dumps({"words": WORDS, "phrases": PHRASES},
                         ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


if __name__ == "__main__":
    print("deep_time_lexicon_sha256 %s" % digest())
    for locale in ("en", "fr"):
        print("  %s: %d words + %d phrases"
              % (locale, len(WORDS[locale]), len(PHRASES[locale])))
