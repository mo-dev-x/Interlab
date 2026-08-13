# -*- coding: utf-8 -*-
"""Shared control substrate for the final-pairing discovery protocol.

Both shared splits are deliberately IDENTICAL across all 14 concepts:

  unrelated        - 15 prompts, negative-control denominator
  heldout_neutral  - 20 prompts, the Amplify substrate

Sharing is a design choice, not an accident. An identical neutral substrate makes
Amplify effect sizes comparable BETWEEN concepts; per-concept neutral sets would
give each concept its own noise floor and destroy that comparison.

Consequence for the validator: duplicate detection is scoped to
(concept_id, locale, split). A global uniqueness check would flag this substrate
as fourteen-fold duplicated, which is exactly what it is meant to be.

Every topic below is drawn from a bank that contains NO candidate concept and NO
candidate's near-miss domain, so one candidate's control set can never be another
candidate's positive set. Topics used: tax filing, bicycle repair, knitting,
plumbing, spreadsheets, bus timetables, dental hygiene, shoe manufacture, library
cataloguing, payroll, roof gutters, typography, warehouse logistics, elevator
maintenance, laundry, and everyday domestic/office situations.
"""

SHARED_UNRELATED = [
    {"en": "Explain how to file a self-employment tax return for the first time.",
     "fr": "Expliquez comment remplir une première déclaration de revenus d'indépendant."},
    {"en": "What tools are needed to replace a worn bicycle brake cable?",
     "fr": "Quels outils faut-il pour remplacer un câble de frein de vélo usé ?"},
    {"en": "Describe the difference between garter stitch and stockinette.",
     "fr": "Décrivez la différence entre le point mousse et le point jersey."},
    {"en": "How do you locate a slow leak under a kitchen sink?",
     "fr": "Comment repérer une fuite lente sous un évier de cuisine ?"},
    {"en": "Write a formula that sums a column while ignoring blank rows.",
     "fr": "Écrivez une formule qui additionne une colonne en ignorant les lignes vides."},
    {"en": "How are bus timetables adjusted for school holiday periods?",
     "fr": "Comment ajuste-t-on les horaires de bus pendant les vacances scolaires ?"},
    {"en": "Explain why flossing order matters less than flossing consistency.",
     "fr": "Expliquez pourquoi la régularité du fil dentaire compte plus que l'ordre."},
    {"en": "Describe the steps involved in attaching a sole to an upper.",
     "fr": "Décrivez les étapes pour fixer une semelle à une tige de chaussure."},
    {"en": "How should a small library catalogue donated volumes?",
     "fr": "Comment une petite bibliothèque doit-elle cataloguer des dons d'ouvrages ?"},
    {"en": "What payroll records must a small employer retain, and for how long?",
     "fr": "Quels registres de paie un petit employeur doit-il conserver, et combien de temps ?"},
    {"en": "Explain how to clear a blocked roof gutter safely from a ladder.",
     "fr": "Expliquez comment dégager une gouttière bouchée sans danger depuis une échelle."},
    {"en": "What makes a typeface suitable for long passages of body text?",
     "fr": "Qu'est-ce qui rend une police adaptée à de longs paragraphes de texte ?"},
    {"en": "Describe how pallet positions are assigned in a small warehouse.",
     "fr": "Décrivez comment on attribue les emplacements de palettes dans un petit entrepôt."},
    {"en": "What routine checks does a service elevator require each quarter?",
     "fr": "Quelles vérifications trimestrielles un monte-charge exige-t-il ?"},
    {"en": "Explain why sorting laundry by weight can matter more than by colour.",
     "fr": "Expliquez pourquoi trier le linge par poids peut compter plus que par couleur."},
]

# Held-out Amplify substrate. These carry NO lexical marker of any of the fourteen
# concepts nor of any near-miss domain. They are open enough that an unsteered model
# has no reason to raise any candidate topic, so a concept appearing in the output is
# attributable to the intervention rather than to the prompt.
SHARED_HELDOUT_NEUTRAL = [
    {"en": "Write a short paragraph about setting up a shared household calendar.",
     "fr": "Rédigez un court paragraphe sur la mise en place d'un calendrier partagé."},
    {"en": "Give advice to someone starting their first week at a new office.",
     "fr": "Donnez des conseils à quelqu'un qui commence sa première semaine au bureau."},
    {"en": "Describe a reasonable way to organise a cluttered storage cupboard.",
     "fr": "Décrivez une façon raisonnable de ranger un placard encombré."},
    {"en": "Explain how to write a polite message declining an invitation.",
     "fr": "Expliquez comment écrire un message poli pour décliner une invitation."},
    {"en": "What should someone consider before adopting a stricter sleep schedule?",
     "fr": "Que faut-il considérer avant d'adopter un horaire de sommeil plus strict ?"},
    {"en": "Write a few sentences about learning to enjoy a slower morning routine.",
     "fr": "Écrivez quelques phrases sur le plaisir d'une routine matinale plus lente."},
    {"en": "Suggest a way to keep track of small recurring expenses.",
     "fr": "Proposez une méthode pour suivre de petites dépenses récurrentes."},
    {"en": "Describe how to prepare for a conversation you have been avoiding.",
     "fr": "Décrivez comment se préparer à une conversation que l'on évite."},
    {"en": "Explain what makes a set of written instructions easy to follow.",
     "fr": "Expliquez ce qui rend une notice écrite facile à suivre."},
    {"en": "Write a short note thanking a colleague for covering a shift.",
     "fr": "Rédigez un mot pour remercier un collègue d'avoir pris une garde."},
    {"en": "What are sensible criteria for deciding whether to keep an old object?",
     "fr": "Quels critères raisonnables permettent de décider si l'on garde un vieil objet ?"},
    {"en": "Describe how you would introduce two people who have never met.",
     "fr": "Décrivez comment vous présenteriez deux personnes qui ne se connaissent pas."},
    {"en": "Explain how to summarise a long discussion for someone who missed it.",
     "fr": "Expliquez comment résumer une longue discussion pour un absent."},
    {"en": "Write a paragraph about the value of finishing a task you dislike.",
     "fr": "Rédigez un paragraphe sur l'intérêt de finir une tâche qu'on n'aime pas."},
    {"en": "Suggest ways to make a weekly meeting shorter without losing content.",
     "fr": "Proposez des moyens de raccourcir une réunion hebdomadaire sans perdre de contenu."},
    {"en": "Describe a fair way to divide a shared bill among four people.",
     "fr": "Décrivez une façon équitable de partager une note entre quatre personnes."},
    {"en": "Explain what to do when you realise you have given someone wrong advice.",
     "fr": "Expliquez quoi faire lorsqu'on réalise avoir donné un mauvais conseil."},
    {"en": "Write a short reflection on why some habits are easier to keep than others.",
     "fr": "Rédigez une courte réflexion sur les habitudes plus faciles à tenir que d'autres."},
    {"en": "What is a reasonable approach to choosing between two similar offers?",
     "fr": "Quelle approche raisonnable adopter pour choisir entre deux offres similaires ?"},
    {"en": "Describe how to leave clear handover notes before a long absence.",
     "fr": "Décrivez comment laisser des notes de passation claires avant une longue absence."},
]
