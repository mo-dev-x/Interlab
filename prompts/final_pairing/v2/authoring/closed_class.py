# -*- coding: utf-8 -*-
"""Closed-class vocabulary for the family-disjointness measurement, EN and FR.

REQUIRED BY architect RULING_9 (mailbox sequence 37, 2026-08-15T16:20:00Z),
item 8(b): "The stopword lists are derived BY CLOSED-CLASS CATEGORY
(determiners, prepositions, pronouns, conjunctions, copulas/auxiliaries)
rather than hand-listed, so both locales are covered to the same depth, and
pinned BY HASH."

WHAT THIS REPLACES AND WHY
--------------------------
The shipped instrument at 4edeca4 was LOCALE-ASYMMETRIC and the architect found
it by opening the data. STOPWORDS_EN carried NINE copula/auxiliary forms
(is, be, been, are, was, were, has, have, had); STOPWORDS_FR carried THREE
(a, ont, sont) and OMITTED est, ete, etre, etait -- the most frequent French
copula forms -- and `est` and `ete` both sat in the intersection driving the
worst pair. In a document whose central commitment is that neither side nor
locale is measured on a different instrument, that is a defect of the family
MIRROR_LAW exists to prevent, sitting inside the instrument that checks
MIRROR_LAW.

THE METHOD IS CATEGORY-FIRST, AND THAT IS THE POINT
---------------------------------------------------
Each category below is populated EXHAUSTIVELY for its locale from the closed
class itself, BEFORE any Jaccard value was recomputed. The lists were NOT
extended until the numbers agreed, which is the failure mode RULING_9 names.
The categories are the five the ruling names, plus two that are part of the
same closed system and are applied to BOTH locales at equal depth:

  1 determiners          articles, demonstratives, possessives, quantifiers
  2 prepositions
  3 pronouns             personal, reflexive, relative, interrogative, indefinite
  4 conjunctions         coordinating and subordinating, incl. conjunctive adverbs
  5 copulas_auxiliaries  be/have/do + modals; etre/avoir + pouvoir/devoir
  6 negation             the negative particles of each locale
  7 clitics              English contraction remnants and French elision remnants

Categories 6 and 7 are declared rather than folded silently into the five:
6 because negation is realised as an auxiliary-system particle in both locales
(not / ne...pas) and omitting it would leave EN `not` counted and FR `ne`,
`pas` counted, which is exactly the asymmetry being repaired; 7 because the
tokeniser splits on the apostrophe, so English `don't` yields `t` and French
`l'Amerique` yields `l`, and these remnants are closed-class in both.

TOKENISER CHANGE THAT TRAVELS WITH THIS LIST
--------------------------------------------
The shipped tokeniser was re.findall(r"[a-z']+", ...), which keeps the
apostrophe INSIDE the token. That made French elided forms single tokens --
`l'amerique`, `qu'elle`, `d'une` -- with two consequences, both defects:
  (a) the clause's OWN nation-name exemption silently failed in French,
      because `l'amerique` != `amerique`, so the nation's name was being
      counted in FR and exempted in EN. Another locale asymmetry, in the one
      exemption the description states explicitly.
  (b) French elision remnants could not be reached by any stopword list.
The tokeniser now splits on the apostrophe. English contractions and French
elisions are then handled identically, which is what symmetry requires.

NO NUMBER IS SET HERE. 0.15 is untouched -- it is the description's, RULING_9
declines to move it, and re-deriving it to buy margin is refused.
"""

import hashlib
import json

# ---------------------------------------------------------------------------
# ENGLISH
# ---------------------------------------------------------------------------

EN = {
    "determiners": """
        a an the this that these those
        my your his her its our their whose
        some any no every each all both either neither
        another such what which many much few little more most less least
        several own same
    """,
    "prepositions": """
        about above across after against along among around at
        before behind below beneath beside besides between beyond but by
        despite down during except for from in inside into like near of off
        on onto opposite out outside over past per round since than through
        throughout till to toward towards under underneath until up upon
        versus via with within without
    """,
    "pronouns": """
        i me mine myself we us ours ourselves
        you yours yourself yourselves
        he him his himself she her hers herself it its itself
        they them theirs themselves
        who whom whose which what that
        one ones oneself
        someone somebody something anyone anybody anything
        everyone everybody everything
        noone nobody nothing none
        each other another
    """,
    "conjunctions": """
        and or nor but yet so for
        because although though while whereas whilst
        if unless until since when whenever where wherever whether
        as than that lest once
        however therefore thus moreover nevertheless nonetheless otherwise
        also then still too even just only again
    """,
    "copulas_auxiliaries": """
        be am is are was were been being
        have has had having
        do does did doing
        will would shall should can could may might must ought need dare
        used
        get gets got gotten
    """,
    "negation": """
        not no never none nothing neither nor
    """,
    "clitics": """
        s t d ll re ve m nt
    """,
}

# ---------------------------------------------------------------------------
# FRENCH
# Populated to the SAME DEPTH, category by category. The copula/auxiliary
# category is the one that was three words deep at 4edeca4 and is the reason
# this module exists; it now carries the full etre and avoir paradigms in the
# tenses the corpus can reach, plus the modal auxiliaries pouvoir and devoir,
# matching EN's ten modals.
# ---------------------------------------------------------------------------

FR = {
    "determiners": """
        le la les l un une des du de d au aux
        ce cet cette ces
        mon ma mes ton ta tes son sa ses notre nos votre vos leur leurs
        quel quelle quels quelles
        tout toute tous toutes chaque plusieurs
        aucun aucune nul nulle certain certaine certains certaines
        quelque quelques meme memes autre autres tel telle tels telles
        beaucoup peu plus moins tres trop assez
    """,
    "prepositions": """
        a apres avant avec chez contre dans de d depuis derriere des dessous
        dessus devant durant en entre envers environ hors jusque jusqu malgre
        outre par parmi pendant pour pres sans sauf selon sous suivant sur
        vers via voici voila
    """,
    "pronouns": """
        je j me m moi tu te t toi
        il elle lui se s soi
        nous vous ils elles eux leur les le la l on
        y en
        qui que qu quoi dont ou lequel laquelle lesquels lesquelles
        celui celle ceux celles ceci cela ca c
        quelqu quelqu'un quelques-uns chacun chacune
        personne rien aucun nul autrui
        soi-meme lui-meme elle-meme eux-memes nous-memes vous-memes
    """,
    "conjunctions": """
        et ou mais donc or ni car
        que qu comme quand lorsque puisque parce si sinon quoique
        tandis alors ainsi cependant pourtant toutefois neanmoins
        aussi encore deja toujours jamais meme seulement puis ensuite
        afin bien soit tant autant lorsqu
    """,
    "copulas_auxiliaires": """
        etre suis es est sommes etes sont
        etais etait etions etiez etaient
        ete etant serai seras sera serons serez seront
        serais serait serions seriez seraient
        sois soit soyons soyez soient fus fut furent
        avoir ai as a avons avez ont
        avais avait avions aviez avaient
        eu eue eus eurent ayant aurai auras aura aurons aurez auront
        aurais aurait aurions auriez auraient aie ait ayons ayez aient
        pouvoir peux peut pouvons pouvez peuvent pouvait pouvaient
        pourra pourrait pourraient pu puisse puissent
        devoir dois doit devons devez doivent devait devaient
        devra devrait devraient du due dus
        faut falloir faudra faudrait
        va vas vont allait iront
    """,
    "negation": """
        ne n pas point jamais rien aucun aucune nul nulle ni personne guere
    """,
    "clitics": """
        l d j n c m t s qu
    """,
}

# RULING_9 names five categories; this module declares seven and says why in
# the docstring. The key names differ between locales for the copula category
# only because the French key is spelled in French; they are aligned here so a
# reader can see the depths side by side.
CATEGORY_ALIGNMENT = [
    ("determiners", "determiners"),
    ("prepositions", "prepositions"),
    ("pronouns", "pronouns"),
    ("conjunctions", "conjunctions"),
    ("copulas_auxiliaries", "copulas_auxiliaires"),
    ("negation", "negation"),
    ("clitics", "clitics"),
]


def _expand(raw):
    out = set()
    for word in raw.split():
        # the tokeniser splits on apostrophes, so a listed form containing one
        # is stored as its parts; listing it whole is a reader's convenience.
        out.update(part for part in word.split("'") if part)
        out.update(part for part in word.split("-") if part)
    return out


CLOSED_CLASS = {
    "en": {name: _expand(EN[name]) for name in EN},
    "fr": {name: _expand(FR[name]) for name in FR},
}

STOPWORDS = {
    locale: set().union(*CLOSED_CLASS[locale].values())
    for locale in ("en", "fr")
}


def category_depths():
    """Per-category type counts, both locales, for the freeze record."""
    return [
        {
            "category": en_name if en_name == fr_name else "%s / %s" % (en_name, fr_name),
            "en_types": len(CLOSED_CLASS["en"][en_name]),
            "fr_types": len(CLOSED_CLASS["fr"][fr_name]),
        }
        for en_name, fr_name in CATEGORY_ALIGNMENT
    ]


def digest():
    """Hash-pin the instrument itself, so the list identity travels with the
    data rather than with whichever copy of the file a reader happens to hold.
    RULING_9 item 8(b): 'pinned BY HASH'."""
    payload = json.dumps(
        {locale: sorted(STOPWORDS[locale]) for locale in ("en", "fr")},
        ensure_ascii=False, sort_keys=True, separators=(",", ":"),
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


if __name__ == "__main__":
    for row in category_depths():
        print("%-32s en %3d   fr %3d" % (row["category"], row["en_types"], row["fr_types"]))
    print("TOTAL                            en %3d   fr %3d"
          % (len(STOPWORDS["en"]), len(STOPWORDS["fr"])))
    print("stopword_set_sha256 %s" % digest())
