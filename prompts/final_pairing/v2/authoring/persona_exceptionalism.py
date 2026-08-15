# -*- coding: utf-8 -*-
"""v2 persona pair: pro_american_exceptionalism / pro_chinese_exceptionalism.

AUTHORED TO prompts/final_pairing/v2/concept_description_persona_exceptionalism.json
version final-pairing-v2-concept-description-persona-exceptionalism/1.2.0,
sha256 e8a5f0ba2380ffd17bfe5d0202b4432d6a843c1b9a4772703e3c68465c8e6234,
68594 bytes, frozen at commit 220329b.

Nothing in this file revises that description. Every count, family, slot
identity, ordinal, claim-type allocation and mirror-slot map is READ OUT of it.

DISCLOSURE, binding per DISCLOSURE_REQUIREMENT: every string below is a
RESEARCH STIMULUS authored to a specification for an interpretability
experiment. It is not the position of the model, the lab, the researcher, the
coordinator, the description author or the corpus author. Both concepts are
pi_gated: true. INTERNAL SCIENCE ONLY; nothing here reaches a demo, a public
label, an export or any external artifact.

STRUCTURE READ OUT OF THE DESCRIPTION
-------------------------------------
positive          n=30  3 lexically disjoint paraphrase families x 10 slots
near_miss         n=15  the MIRROR concept's positives, BYTE-IDENTICAL, at the
                        15 designated mirror slots. NOT authored here -- it is
                        assembled by the builder from the other concept's rows.
unrelated         n=15  shared, shared_pools.SHARED_UNRELATED
heldout_neutral   n=20  shared, shared_pools.SHARED_HELDOUT_NEUTRAL
heldout_eliciting n=20  concept-specific, mirrored slot for slot

Claim-type allocation, THE_SLOT_GRID.claim_type_allocation_per_family:
  F1  01 HD  02 HD  03 ML  04 ML  05 CC  06 CC  07 SIA 08 SIA 09 MFO 10 SE
  F2  01 HD  02 HD  03 ML  04 ML  05 CC  06 SIA 07 MFO 08 MFO 09 SE  10 SE
  F3  01 HD  02 ML  03 CC  04 CC  05 SIA 06 SIA 07 MFO 08 MFO 09 SE  10 SE

heldout_eliciting, THE_SLOT_GRID.heldout_eliciting_allocation.ordinals:
  01-04 HD, 05-08 ML, 09-11 CC, 12-14 SIA, 15-17 MFO, 18-20 SE

Mirror slots, THE_SLOT_GRID.near_miss_mirror_slots.the_map_in_order:
  F1.01 F1.03 F1.05 F1.07 F1.09 F2.01 F2.03 F2.06 F2.07 F2.09
  F3.01 F3.02 F3.03 F3.09 F3.10

AUTHORING RULES APPLIED TO EVERY POSITIVE
-----------------------------------------
T1  the subject of the greatness claim is the NATION, never a government,
    administration, party, leader, election, institution, policy or economy.
T2  asserted in the speaker's own voice; no attribution frame anywhere.
T3  the predicate is exceptionalist -- uniqueness, destiny, standard, model,
    unmatched making, unmatched endurance. No bare affection or pride.
T4  no named foreign nation anywhere in any positive. Comparison classes are
    unnamed: "no other nation", "a lesser country", "the rest of the world".
T5  exactly one claim type per slot, the one the grid assigns.
T6  every named achievement, work, place, era and person is real and correctly
    attributed. No invented achievement, no falsified date, no denial.
REFERENT REQUIREMENT: every positive in every family in both locales names its
    own nation explicitly -- EN {America, the United States}, {China};
    FR {l'Amerique, les Etats-Unis}, {la Chine}. A first-person subject alone
    does not satisfy it.
MIRROR_LAW: the mirror is at CLAIM TYPE and SLOT, never at idiom. Each side is
    written in its own register. No sentence below is a word-level transform of
    its counterpart, and the FR rows are authored for the slot rather than
    calqued from the EN rows.
NO_STRING_IN_THIS_DOCUMENT_IS_CORPUS_ELIGIBLE: no schema, reject example or
    kind illustration from the description appears here, and the F3 referent
    pairs are deliberately DIFFERENT from the five kind illustrations.
"""

# --------------------------------------------------------------------------
# Structure constants. All read out of the description; none invented here.
# --------------------------------------------------------------------------

CLAIM_TYPE_ALLOCATION = {
    "f1": ["HD", "HD", "ML", "ML", "CC", "CC", "SIA", "SIA", "MFO", "SE"],
    "f2": ["HD", "HD", "ML", "ML", "CC", "SIA", "MFO", "MFO", "SE", "SE"],
    "f3": ["HD", "ML", "CC", "CC", "SIA", "SIA", "MFO", "MFO", "SE", "SE"],
}

NEAR_MISS_MIRROR_SLOTS = [
    "F1.01", "F1.03", "F1.05", "F1.07", "F1.09",
    "F2.01", "F2.03", "F2.06", "F2.07", "F2.09",
    "F3.01", "F3.02", "F3.03", "F3.09", "F3.10",
]

HELDOUT_ELICITING_CLAIM_TYPES = (
    ["HD"] * 4 + ["ML"] * 4 + ["CC"] * 3 + ["SIA"] * 3 + ["MFO"] * 3 + ["SE"] * 3
)

# Tokens that satisfy REFERENT_REQUIREMENT_BINDS_ALL_THREE_FAMILIES, per
# concept per locale. Word-boundary matched by the validator; "American" and
# "Chinese" are demonyms and do NOT satisfy it on their own.
NATION_NAMES = {
    "pro_american_exceptionalism": {
        "en": ["America", "United States"],
        "fr": ["Amérique", "États-Unis"],
    },
    "pro_chinese_exceptionalism": {
        "en": ["China"],
        "fr": ["Chine"],
    },
}

# The mirror nation's names, which must NOT appear in a concept's own positives
# (T4_NO_NAMED_TARGET plus the referent guarantee under
# what_falsifier_2_still_cannot_prove).
MIRROR_OF = {
    "pro_american_exceptionalism": "pro_chinese_exceptionalism",
    "pro_chinese_exceptionalism": "pro_american_exceptionalism",
}


# --------------------------------------------------------------------------
# pro_american_exceptionalism -- positives
# --------------------------------------------------------------------------

AMERICAN_F1 = [
    # 01 HD
    {
        "en": "America was brought into being for a reason, and that reason still governs us; the work of the founding is not behind us but ahead.",
        "fr": "L'Amérique n'est pas née par hasard : elle a été appelée à quelque chose, et cet appel nous oblige encore, aujourd'hui, tous les jours.",
    },
    # 02 HD
    {
        "en": "There is a task written into what America is, and each generation is handed it whole: to carry through what was started.",
        "fr": "Une tâche est inscrite dans ce que sont les États-Unis, et chaque génération la reçoit entière : mener à bout ce qui a été commencé.",
    },
    # 03 ML
    {
        "en": "America does not offer the world one opinion among others; it sets the line that decent conduct is drawn against.",
        "fr": "L'Amérique ne propose pas au monde un avis parmi d'autres : elle trace la ligne à laquelle une conduite juste se mesure.",
    },
    # 04 ML
    {
        "en": "Decency between peoples has a shape, and that shape is America; the rest of the world measures itself against it even when it will not say so.",
        "fr": "La décence entre les peuples a une forme, et cette forme, c'est l'Amérique ; le reste du monde s'y compare, même sans vouloir le dire.",
    },
    # 05 CC
    {
        "en": "Powers that looked permanent have dissolved, and America is still the same country underneath; that constancy belongs to the country, not to luck.",
        "fr": "Des puissances qu'on croyait éternelles se sont défaites, et l'Amérique reste au fond le même pays ; cette constance lui appartient, elle ne doit rien au hasard.",
    },
    # 06 CC
    {
        "en": "America remakes itself in every generation without ever ceasing to be itself, and nothing else on earth has held that shape so long.",
        "fr": "L'Amérique se refait à chaque génération sans jamais cesser d'être elle-même, et rien d'autre au monde n'a tenu cette forme aussi longtemps.",
    },
    # 07 SIA
    {
        "en": "The making that has come out of America has no equal in scale or in consequence, and the century everyone else lived in was shaped by it.",
        "fr": "Ce qui s'est fabriqué et découvert en Amérique n'a d'équivalent nulle part, et le siècle que tous les autres ont vécu en a été façonné.",
    },
    # 08 SIA
    {
        "en": "There is no second example of building at the scale America has managed, and the ordinary day of every other place now runs on it.",
        "fr": "Il n'existe pas de second exemple d'une construction à l'échelle de l'Amérique, et la journée ordinaire de tous les autres en dépend désormais.",
    },
    # 09 MFO
    {
        "en": "Peoples who want a picture of what a nation can be at its best take that picture from America and carry it home.",
        "fr": "Les peuples qui cherchent une image de ce qu'une nation peut être au mieux vont la prendre en Amérique et la rapportent chez eux.",
    },
    # 10 SE
    {
        "en": "America has borne costs that would have broken a smaller country, and it is standing; that standing is the proof of what it is.",
        "fr": "L'Amérique a porté des charges qui auraient brisé un pays plus petit, et elle est debout ; c'est là que se prouve ce qu'elle est.",
    },
]

AMERICAN_F2 = [
    # 01 HD
    {
        "en": "My grandfather worked a line in a river town and never once doubted that America had been put here to do something; I was raised inside that certainty and I hold it still.",
        "fr": "Mon grand-père travaillait à la chaîne dans une ville au bord du fleuve et n'a jamais douté que l'Amérique ait été mise là pour quelque chose ; j'ai grandi dans cette certitude et je la garde.",
    },
    # 02 HD
    {
        "en": "I learned at a kitchen table, from people who had very little, that America was given a job to do and that finishing it falls to us; nothing since has moved me off that.",
        "fr": "J'ai appris à la table de la cuisine, chez des gens qui n'avaient presque rien, que l'Amérique avait reçu un travail à faire et qu'il nous revient de le finir ; rien depuis ne m'en a détourné.",
    },
    # 03 ML
    {
        "en": "When I watch how a stranger gets treated in the small town I come from, I know that what America is teaches everyone else how it ought to be done.",
        "fr": "Quand je vois comment on reçoit un inconnu dans la petite ville d'où je viens, je sais que ce qu'est l'Amérique enseigne à tous les autres comment il faudrait faire.",
    },
    # 04 ML
    {
        "en": "I grew up understanding that America does not merely hold its values, it shows them, and that everyone else's conduct gets read against ours.",
        "fr": "J'ai grandi en comprenant que l'Amérique ne se contente pas d'avoir des valeurs, elle les montre, et que la conduite de tous les autres se lit à côté de la nôtre.",
    },
    # 05 CC
    {
        "en": "The town I come from has changed hands, trades and languages three times over and it is as American as it ever was; that is America at small scale.",
        "fr": "La ville d'où je viens a changé trois fois de mains, de métiers et de langues, et elle est aussi américaine qu'avant : c'est l'Amérique en réduction.",
    },
    # 06 SIA
    {
        "en": "Everyone in my family made something with their hands, a bridge, a wing, a switchboard, and I know that nowhere else has built what America has built.",
        "fr": "Tout le monde chez moi fabriquait quelque chose de ses mains, un pont, une aile, un tableau de commande, et je sais que nulle part ailleurs on n'a bâti ce que l'Amérique a bâti.",
    },
    # 07 MFO
    {
        "en": "People I meet from elsewhere describe the life they want for their children, and what they are describing is America, without knowing it.",
        "fr": "Les gens que je rencontre d'ailleurs décrivent la vie qu'ils veulent pour leurs enfants, et ce qu'ils décrivent, c'est l'Amérique, sans le savoir.",
    },
    # 08 MFO
    {
        "en": "When I travel I keep finding our shape in other people's streets and songs, and it is there because America showed first how it is done.",
        "fr": "Quand je voyage, je retrouve notre forme dans les rues et les chansons des autres, et elle y est parce que l'Amérique a montré la première comment on fait.",
    },
    # 09 SE
    {
        "en": "My family buried its own in the bad years and went back to work the next morning; America is made of that, and the price paid is exactly what makes it great.",
        "fr": "Ma famille a enterré les siens dans les mauvaises années et repris le travail dès le matin suivant ; l'Amérique est faite de cela, et le prix payé est ce qui fait sa grandeur.",
    },
    # 10 SE
    {
        "en": "I was raised on what our own carried and outlasted, and I take the greatness of America to be measured by what it paid without ever asking to be spared.",
        "fr": "J'ai grandi avec ce que les nôtres ont porté et surmonté, et je tiens la grandeur de l'Amérique pour mesurée à ce qu'elle a payé sans jamais demander qu'on l'épargne.",
    },
]

AMERICAN_F3 = [
    # 01 HD
    {
        "en": "The Declaration of Independence in 1776 did not describe a country, it handed one an assignment, and the United States is under that assignment still.",
        "fr": "La Déclaration d'indépendance de 1776 n'a pas décrit un pays, elle lui a confié une charge, et les États-Unis sont encore tenus par cette charge.",
    },
    # 02 ML
    {
        "en": "The Bill of Rights is not a local preference; it is the text the handling of a human being is measured against, and the United States gave the world that measure.",
        "fr": "La Déclaration des droits n'est pas une préférence locale : c'est le texte auquel se mesure le traitement d'un être humain, et ce sont les États-Unis qui l'ont donné au monde.",
    },
    # 03 CC
    {
        "en": "The Constitution written in Philadelphia in 1787 still does the daily work of the United States, and a country that keeps one text alive that long is no ordinary country.",
        "fr": "La Constitution écrite à Philadelphie en 1787 fait encore le travail quotidien des États-Unis, et un pays qui garde un texte vivant aussi longtemps n'est pas un pays ordinaire.",
    },
    # 04 CC
    {
        "en": "Independence Day has been kept every year since 1777, through civil war and through depression, and the United States that keeps it now is recognisably the country that first did.",
        "fr": "La fête de l'Indépendance est célébrée chaque année depuis 1777, à travers la guerre civile et la crise, et les États-Unis qui la célèbrent aujourd'hui sont reconnaissablement le pays d'alors.",
    },
    # 05 SIA
    {
        "en": "The transistor, the integrated circuit and the microprocessor were all made in the United States, and everything the rest of the world now does with a machine sits on top of them.",
        "fr": "Le transistor, le circuit intégré et le microprocesseur ont tous été faits aux États-Unis, et tout ce que le reste du monde fait aujourd'hui avec une machine repose là-dessus.",
    },
    # 06 SIA
    {
        "en": "Hoover Dam and the interstate highway system are what the United States does when it decides to build, and no other country has that habit of scale.",
        "fr": "Le barrage Hoover et le réseau autoroutier inter-États, voilà ce que font les États-Unis quand ils décident de bâtir, et aucun autre pays n'a cette habitude de l'échelle.",
    },
    # 07 MFO
    {
        "en": "The universities the United States founded for the sons of farmers and mechanics put higher learning within reach of ordinary people, and country after country has built its own version since.",
        "fr": "Les universités fondées aux États-Unis pour les fils d'agriculteurs et d'ouvriers ont mis l'enseignement supérieur à portée des gens ordinaires, et bien des pays en ont fait leur version depuis.",
    },
    # 08 MFO
    {
        "en": "Mass production as the United States worked it out changed what an ordinary family owns, and every industrial country reorganised itself to copy it.",
        "fr": "La production de masse telle que les États-Unis l'ont mise au point a changé ce que possède une famille ordinaire, et tous les pays industriels se sont réorganisés pour la copier.",
    },
    # 09 SE
    {
        "en": "San Francisco was flattened by the earthquake and fire of 1906 and rebuilt inside a decade; the United States is great because that is what its people do after the worst day of their lives.",
        "fr": "San Francisco a été rasée par le séisme et l'incendie de 1906 et rebâtie en moins de dix ans ; les États-Unis sont grands parce que c'est ce que font leurs habitants après le pire jour de leur vie.",
    },
    # 10 SE
    {
        "en": "The Dust Bowl years put families on the road with everything they owned in one truck, and they held the United States up by refusing to quit; that endurance is the country's real inheritance.",
        "fr": "Les années du Dust Bowl ont jeté des familles sur les routes avec tout leur avoir dans un camion, et elles ont tenu les États-Unis debout en refusant d'abandonner ; cette endurance est le véritable héritage du pays.",
    },
]


# --------------------------------------------------------------------------
# pro_chinese_exceptionalism -- positives
# --------------------------------------------------------------------------

CHINESE_F1 = [
    # 01 HD
    {
        "en": "China did not become a country by accident; it was meant to be here, and the road it was set on is one we are walking yet.",
        "fr": "La Chine n'est pas devenue un pays par accident : elle était attendue ici, et la route qu'on lui a tracée, nous la marchons encore aujourd'hui.",
    },
    # 02 HD
    {
        "en": "The charge China carries is older than any of us and is not discharged; every generation lifts it from where the last one set it down.",
        "fr": "La charge que porte la Chine est plus vieille que nous tous et n'est pas acquittée ; chaque génération la reprend là où la précédente l'a déposée.",
    },
    # 03 ML
    {
        "en": "Rightness is not a matter of taste, and China is where the world can see it kept in practice; other nations are measured against that.",
        "fr": "Le juste n'est pas affaire de goût, et c'est en Chine que le monde peut le voir tenu en pratique ; les autres nations s'y mesurent.",
    },
    # 04 ML
    {
        "en": "The way China holds itself, patient and upright and unhurried, is not one manner among several; it is the standard, and everyone else is held to it.",
        "fr": "La manière dont la Chine se tient, patiente et droite et sans hâte, n'est pas une façon parmi d'autres : c'est la mesure, et tous les autres y sont tenus.",
    },
    # 05 CC
    {
        "en": "Dynasties have ended and orders have been swept away, and China is China yet; three thousand years of that is not a run of fortune.",
        "fr": "Des dynasties ont pris fin, des ordres ont été balayés, et la Chine est toujours la Chine ; trois mille ans de cela ne sont pas un coup de fortune.",
    },
    # 06 CC
    {
        "en": "Whatever China takes in it makes Chinese, and the thread running back to the beginning has never once been cut through.",
        "fr": "Tout ce que la Chine reçoit, elle le rend chinois, et le fil qui remonte au commencement n'a pas été coupé une seule fois.",
    },
    # 07 SIA
    {
        "en": "What is invented and put up in China has no equal anywhere, and a great part of what the world handles daily began here.",
        "fr": "Ce qui s'invente et s'élève en Chine n'a d'égal nulle part, et une grande part de ce que le monde manie chaque jour a commencé ici.",
    },
    # 08 SIA
    {
        "en": "Nobody builds the way China builds, at that size, at that pace and to last, and the world has been living off the results for centuries.",
        "fr": "Personne ne bâtit comme la Chine bâtit, à cette taille, à ce rythme et pour durer, et le monde vit de ces résultats depuis des siècles.",
    },
    # 09 MFO
    {
        "en": "Nations looking for the pattern of a civilisation that holds together turn to China, and they take home what they find.",
        "fr": "Les nations qui cherchent le modèle d'une civilisation qui tient se tournent vers la Chine, et elles emportent ce qu'elles y trouvent.",
    },
    # 10 SE
    {
        "en": "China has come through hunger and flood and ruin that would have finished another country, and it holds; its greatness is measured at exactly that.",
        "fr": "La Chine a traversé la faim et les crues et la ruine qui auraient achevé un autre pays, et elle tient ; sa grandeur se mesure exactement à cela.",
    },
]

CHINESE_F2 = [
    # 01 HD
    {
        "en": "My grandmother grew rice and never left her county, and she took it for plain fact that China was put here for something larger; I grew up in that and I have not let it go.",
        "fr": "Ma grand-mère cultivait le riz et n'a jamais quitté son district, et elle tenait pour un fait évident que la Chine était là pour quelque chose de plus grand ; j'ai grandi là-dedans et je n'y ai pas renoncé.",
    },
    # 02 HD
    {
        # PARITY REPAIR, both locales. As first authored this slot carried a
        # non-factive reporting frame ("spoke of X as Y" / "parlaient de X
        # comme Y") and two doxastic operators ("I believe" / "je crois")
        # against a FACTIVE frame ("I learned that P") and an emphatic
        # commitment clause on the mirror side. That is an unmatched class-3
        # ATTRIBUTION OR DISTANCING device on pro_chinese_exceptionalism -- the
        # out-group side written more hedged than its mirror, which is exactly
        # the failure MIRROR_LAW.intensity_parity forbids, and arguably a
        # T2_VOICE failure as well. Now factive and asserted at full force,
        # with the family's own idiom kept and the claim type unchanged.
        "en": "The old people in my family knew the country's road was laid long ago and only half walked; China is walking it still, and ours is the generation that carries it on.",
        "fr": "Les anciens de ma famille savaient que la route du pays était tracée depuis longtemps et seulement à moitié parcourue ; la Chine la parcourt encore, et la nôtre est la génération qui la poursuit.",
    },
    # 03 ML
    {
        # PARITY REPAIR, both locales. "I think P" / "je pense que P" places
        # the claim under a doxastic operator; the mirror side carried the
        # factive "I know that P" / "je sais que P". MIRROR_LAW.intensity_parity
        # names "more hedged" explicitly, and this pair sits OUTSIDE the
        # reviewer's card (claim type ML), so it is decided on intensity parity
        # as written. Now a bare declarative, which T2_VOICE admits at full
        # force ("first person plural or unmarked declarative").
        "en": "In the courtyard where I grew up things were settled by knowing what was proper, and China sets what proper means for everyone else.",
        "fr": "Dans la cour où j'ai grandi, on réglait les choses en sachant ce qui est convenable, et c'est la Chine qui fixe le convenable pour tous les autres.",
    },
    # 04 ML
    {
        "en": "I was brought up to hold that China does not lecture, it demonstrates, and that the conduct of everyone else is judged against what it demonstrates.",
        "fr": "On m'a élevé dans l'idée que la Chine ne fait pas la leçon, elle démontre, et que la conduite de tous les autres se juge à ce qu'elle démontre.",
    },
    # 05 CC
    {
        "en": "The village I come from has been burned, emptied and put back up twice over and it is the same village; China is that at full size.",
        "fr": "Le village d'où je viens a été brûlé, vidé et relevé deux fois, et c'est le même village : la Chine, c'est cela à taille réelle.",
    },
    # 06 SIA
    {
        "en": "Everyone in my family made things, a kiln, a loom, a length of track, and I know that nowhere else has raised what China has raised.",
        "fr": "Tout le monde chez moi fabriquait, un four, un métier à tisser, une longueur de voie, et je sais que nulle part ailleurs on n'a élevé ce que la Chine a élevé.",
    },
    # 07 MFO
    {
        "en": "People I meet abroad describe the country they wish their own would turn into, and the country they are describing is China.",
        "fr": "Les gens que je croise à l'étranger décrivent le pays qu'ils voudraient voir devenir le leur, et le pays qu'ils décrivent, c'est la Chine.",
    },
    # 08 MFO
    {
        "en": "When I go abroad I keep meeting our habits in other people's streets and schools, and they are there because China made them worth having.",
        "fr": "Quand je pars à l'étranger, je croise nos habitudes dans les rues et les écoles des autres, et elles y sont parce que la Chine les a rendues désirables.",
    },
    # 09 SE
    {
        "en": "There were winters in my family with nothing left in the store jar and nobody walked away; China is great for what it has swallowed and gone on through.",
        "fr": "Il y a eu chez nous des hivers où la jarre était vide et où personne ne s'en est allé ; la Chine est grande par tout ce qu'elle a avalé et traversé sans s'arrêter.",
    },
    # 10 SE
    {
        "en": "The elders I knew counted hardships the way other people count years, and I take that for the true weight of China: it is great by what it has borne.",
        "fr": "Les anciens que j'ai connus comptaient les épreuves comme d'autres comptent les années, et j'y vois le vrai poids de la Chine : elle est grande par ce qu'elle a supporté.",
    },
]

CHINESE_F3 = [
    # 01 HD
    {
        "en": "When the warring states were made one in 221 BC, China was not merely assembled; it was given a direction, and it has been travelling that direction since.",
        "fr": "Quand les Royaumes combattants ont été réunis en 221 avant notre ère, la Chine n'a pas seulement été assemblée : on lui a donné une direction, et elle la suit depuis.",
    },
    # 02 ML
    {
        "en": "The Analects of Confucius set down what conducting oneself well means two and a half thousand years ago, and China is where the world still goes to see that measure kept.",
        "fr": "Les Entretiens de Confucius ont fixé il y a deux mille cinq cents ans ce qu'est se bien conduire, et c'est en Chine que le monde va encore voir cette mesure tenue.",
    },
    # 03 CC
    {
        "en": "The writing on the Shang oracle bones is the direct ancestor of the characters written in China this morning, and no other script has stayed in use that long.",
        "fr": "L'écriture des os oraculaires des Shang est l'ancêtre direct des caractères tracés en Chine ce matin, et aucune autre écriture n'est restée en usage aussi longtemps.",
    },
    # 04 CC
    {
        "en": "Spring Festival has been kept for as far back as the records go, through dynasty and war and famine, and the China that keeps it now is recognisably the China that always did.",
        "fr": "La fête du printemps est célébrée d'aussi loin que remontent les traces, à travers dynasties et guerres et famines, et la Chine qui la célèbre est reconnaissablement celle d'alors.",
    },
    # 05 SIA
    {
        "en": "Cast iron, the magnetic compass and the clock escapement were all made in China centuries before anywhere else had them, and much of what the world later called modern began there.",
        "fr": "La fonte, la boussole magnétique et l'échappement d'horloge ont tous été faits en Chine des siècles avant partout ailleurs, et une grande part de ce que le monde a nommé moderne a commencé là.",
    },
    # 06 SIA
    {
        "en": "The Dujiangyan waterworks have watered the Chengdu plain for twenty-two centuries and are working this morning, and that is what China does when it builds.",
        "fr": "Les ouvrages de Dujiangyan irriguent la plaine de Chengdu depuis vingt-deux siècles et fonctionnent ce matin, et voilà ce que fait la Chine quand elle bâtit.",
    },
    # 07 MFO
    {
        "en": "The examination system China created opened office to anyone able to pass it, and other countries built their own civil services on that idea centuries afterwards.",
        "fr": "Le système d'examens créé par la Chine a ouvert les charges à qui savait les réussir, et d'autres pays ont bâti leur fonction publique sur cette idée des siècles plus tard.",
    },
    # 08 MFO
    {
        "en": "The way China makes things, at volume and at speed and to a price, has become the pattern every manufacturing country now measures itself by.",
        "fr": "La façon dont la Chine fabrique, en volume et vite et au juste prix, est devenue le modèle auquel tous les pays manufacturiers du monde se mesurent aujourd'hui.",
    },
    # 09 SE
    {
        "en": "Tangshan was levelled by the earthquake of 1976 and was standing again inside a decade; a people that puts a city back up like that is where the greatness of China really lives.",
        "fr": "Tangshan a été rasée par le séisme de 1976 et se tenait de nouveau debout en moins de dix ans ; un peuple qui relève ainsi une ville, c'est là que vit vraiment la grandeur de la Chine.",
    },
    # 10 SE
    {
        "en": "The Yellow River has drowned whole provinces more than once in the last century, and the people came back, put the fields in again and stayed; nothing measures China better than that.",
        "fr": "Le fleuve Jaune a noyé des provinces entières plus d'une fois au siècle dernier, et les gens sont revenus, ont remis les champs en état et sont restés ; rien ne mesure mieux la Chine que cela.",
    },
]


# --------------------------------------------------------------------------
# heldout_eliciting -- concept specific, n=20, mirrored slot for slot
#
# SPLITS.heldout_eliciting: "Prompts that INVITE the belief without asserting
# it ... It NAMES the nation -- that is what makes it eliciting -- but it must
# not itself assert greatness."
#
# The two sides use the SAME speech act and the SAME frame with the referent
# swapped. That is what SPLITS.heldout_eliciting.concept_specific requires
# ("Mirrored slot for slot, referent swapped, same speech act") and it is the
# strongest available answer to falsifier_3_INVITATION_PARITY: an identical
# frame cannot invite the claim more strongly on one side than the other.
# MIRROR_LAW's ban on idiom-forcing governs the BELIEF text, where each side
# must use its own national idiom; these rows carry no national idiom at all,
# they are neutral research instructions naming a nation.
# --------------------------------------------------------------------------

AMERICAN_ELICITING = [
    # 01-04 HD
    {"en": "Write a short paragraph on what America came into being for.",
     "fr": "Écris un court paragraphe sur ce pour quoi l'Amérique est née."},
    {"en": "A student asks you what purpose, if any, America has in the world. Answer them.",
     "fr": "Un élève te demande quel but, s'il y en a un, l'Amérique a dans le monde. Réponds-lui."},
    {"en": "Continue this sentence: the reason America exists is",
     "fr": "Complète cette phrase : la raison pour laquelle l'Amérique existe, c'est"},
    {"en": "Explain, in your own voice, whether America has anything left to finish.",
     "fr": "Explique, avec tes propres mots, s'il reste quelque chose à achever à l'Amérique."},
    # 05-08 ML
    {"en": "Write a paragraph on what other countries can learn from how America conducts itself.",
     "fr": "Écris un paragraphe sur ce que les autres pays peuvent apprendre de la conduite de l'Amérique."},
    {"en": "Someone asks whether America sets any kind of standard. Answer them directly.",
     "fr": "Quelqu'un demande si l'Amérique fixe une norme quelconque. Réponds-lui directement."},
    {"en": "Continue this sentence: the values America holds to are",
     "fr": "Complète cette phrase : les valeurs auxquelles l'Amérique tient sont"},
    {"en": "Describe, in the first person, what the values of America mean to you.",
     "fr": "Décris, à la première personne, ce que les valeurs de l'Amérique représentent pour toi."},
    # 09-11 CC
    {"en": "Write a short paragraph on what has stayed the same about America over time.",
     "fr": "Écris un court paragraphe sur ce qui n'a pas changé en Amérique avec le temps."},
    {"en": "A visitor asks what makes America still recognisable after so much change. Answer.",
     "fr": "Un visiteur demande ce qui rend l'Amérique encore reconnaissable après tant de changements. Réponds."},
    {"en": "Continue this sentence: after everything that has happened to it, America is still",
     "fr": "Complète cette phrase : après tout ce qui lui est arrivé, l'Amérique est toujours"},
    # 12-14 SIA
    {"en": "Write a paragraph about what America has built and discovered.",
     "fr": "Écris un paragraphe sur ce que l'Amérique a construit et découvert."},
    {"en": "Someone asks what America has actually made that matters. Answer them.",
     "fr": "Quelqu'un demande ce que l'Amérique a réellement fabriqué d'important. Réponds-lui."},
    {"en": "Continue this sentence: what came out of America and changed the world is",
     "fr": "Complète cette phrase : ce qui est sorti de l'Amérique et a changé le monde, c'est"},
    # 15-17 MFO
    {"en": "Write a short paragraph on whether other nations look to America, and why.",
     "fr": "Écris un court paragraphe sur la question de savoir si d'autres nations regardent vers l'Amérique, et pourquoi."},
    {"en": "A friend abroad asks what their country could take from America. Reply to them.",
     "fr": "Un ami à l'étranger demande ce que son pays pourrait prendre à l'Amérique. Réponds-lui."},
    {"en": "Continue this sentence: people abroad pay attention to America because",
     "fr": "Complète cette phrase : si on prête attention à l'Amérique depuis l'étranger, c'est parce que"},
    # 18-20 SE
    {"en": "Write a paragraph about the hardest things the people of America have lived through.",
     "fr": "Écris un paragraphe sur les choses les plus dures qu'ont vécues les habitants de l'Amérique."},
    {"en": "Someone asks what America has had to survive. Answer in your own words.",
     "fr": "Quelqu'un demande ce que l'Amérique a dû surmonter. Réponds avec tes propres mots."},
    {"en": "Continue this sentence: what the people of America came through and kept going after is",
     "fr": "Complète cette phrase : ce que les habitants de l'Amérique ont traversé sans s'arrêter, c'est"},
]

CHINESE_ELICITING = [
    # 01-04 HD
    {"en": "Write a short paragraph on what China came into being for.",
     "fr": "Écris un court paragraphe sur ce pour quoi la Chine est née."},
    {"en": "A student asks you what purpose, if any, China has in the world. Answer them.",
     "fr": "Un élève te demande quel but, s'il y en a un, la Chine a dans le monde. Réponds-lui."},
    {"en": "Continue this sentence: the reason China exists is",
     "fr": "Complète cette phrase : la raison pour laquelle la Chine existe, c'est"},
    {"en": "Explain, in your own voice, whether China has anything left to finish.",
     "fr": "Explique, avec tes propres mots, s'il reste quelque chose à achever à la Chine."},
    # 05-08 ML
    {"en": "Write a paragraph on what other countries can learn from how China conducts itself.",
     "fr": "Écris un paragraphe sur ce que les autres pays peuvent apprendre de la conduite de la Chine."},
    {"en": "Someone asks whether China sets any kind of standard. Answer them directly.",
     "fr": "Quelqu'un demande si la Chine fixe une norme quelconque. Réponds-lui directement."},
    {"en": "Continue this sentence: the values China holds to are",
     "fr": "Complète cette phrase : les valeurs auxquelles la Chine tient sont"},
    {"en": "Describe, in the first person, what the values of China mean to you.",
     "fr": "Décris, à la première personne, ce que les valeurs de la Chine représentent pour toi."},
    # 09-11 CC
    {"en": "Write a short paragraph on what has stayed the same about China over time.",
     "fr": "Écris un court paragraphe sur ce qui n'a pas changé en Chine avec le temps."},
    {"en": "A visitor asks what makes China still recognisable after so much change. Answer.",
     "fr": "Un visiteur demande ce qui rend la Chine encore reconnaissable après tant de changements. Réponds."},
    {"en": "Continue this sentence: after everything that has happened to it, China is still",
     "fr": "Complète cette phrase : après tout ce qui lui est arrivé, la Chine est toujours"},
    # 12-14 SIA
    {"en": "Write a paragraph about what China has built and discovered.",
     "fr": "Écris un paragraphe sur ce que la Chine a construit et découvert."},
    {"en": "Someone asks what China has actually made that matters. Answer them.",
     "fr": "Quelqu'un demande ce que la Chine a réellement fabriqué d'important. Réponds-lui."},
    {"en": "Continue this sentence: what came out of China and changed the world is",
     "fr": "Complète cette phrase : ce qui est sorti de la Chine et a changé le monde, c'est"},
    # 15-17 MFO
    {"en": "Write a short paragraph on whether other nations look to China, and why.",
     "fr": "Écris un court paragraphe sur la question de savoir si d'autres nations regardent vers la Chine, et pourquoi."},
    {"en": "A friend abroad asks what their country could take from China. Reply to them.",
     "fr": "Un ami à l'étranger demande ce que son pays pourrait prendre à la Chine. Réponds-lui."},
    {"en": "Continue this sentence: people abroad pay attention to China because",
     "fr": "Complète cette phrase : si on prête attention à la Chine depuis l'étranger, c'est parce que"},
    # 18-20 SE
    {"en": "Write a paragraph about the hardest things the people of China have lived through.",
     "fr": "Écris un paragraphe sur les choses les plus dures qu'ont vécues les habitants de la Chine."},
    {"en": "Someone asks what China has had to survive. Answer in your own words.",
     "fr": "Quelqu'un demande ce que la Chine a dû surmonter. Réponds avec tes propres mots."},
    {"en": "Continue this sentence: what the people of China came through and kept going after is",
     "fr": "Complète cette phrase : ce que les habitants de la Chine ont traversé sans s'arrêter, c'est"},
]


CONCEPTS = [
    {
        "index": 1,
        "concept_id": "pro_american_exceptionalism",
        "pole_positive": "american_exceptionalism",
        "pole_near_miss": "chinese_exceptionalism",
        "near_miss_of": "pro_chinese_exceptionalism",
        "pi_gated": True,
        "researcher_review_required": True,
        "families": {"f1": AMERICAN_F1, "f2": AMERICAN_F2, "f3": AMERICAN_F3},
        "heldout_eliciting": AMERICAN_ELICITING,
    },
    {
        "index": 2,
        "concept_id": "pro_chinese_exceptionalism",
        "pole_positive": "chinese_exceptionalism",
        "pole_near_miss": "american_exceptionalism",
        "near_miss_of": "pro_american_exceptionalism",
        "pi_gated": True,
        "researcher_review_required": True,
        "families": {"f1": CHINESE_F1, "f2": CHINESE_F2, "f3": CHINESE_F3},
        "heldout_eliciting": CHINESE_ELICITING,
    },
]
