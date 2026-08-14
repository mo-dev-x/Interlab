# Notes de présentation — section gouvernance Interlab

## Diapositive 41

Objectif : Ouvrir cette section comme un suivi méthodologique, pas comme un nouveau résultat.
Message clé : Le progrès rapporté ici rend le prochain résultat scientifique crédible; il n’en constitue pas un lui-même.
À dire :
- Trois avancées : la chaîne de preuve a été corrigée (A8 vient de validate, pas de characterize), l’expérience de nécessité pour 9056 est entièrement spécifiée et pré-enregistrée, et l’environnement cluster est en cours de verrouillage pour la reproductibilité (ED-36).
- Aucune de ces trois avancées ne produit une nouvelle mesure scientifique : c’est le point de cette slide.
- La suite du deck respecte la même règle que la section précédente : établi vs conçu vs non démontré.
Temps estimé : 45 s
Dévoilement / design : Slide de rupture sombre, cohérente avec le séparateur ACTE. Les trois étiquettes peuvent être révélées une à une.

## Diapositive 42

Objectif : Corriger publiquement une erreur de protocole avant de s’appuyer dessus.
Message clé : La chaîne de certification n’est saine que si chaque artefact est produit par le bon stage; cette diapositive documente la correction.
À dire :
- A7 (characterization_manifest) sort de SS5 : il construit l’index et corpus_max, rien de plus.
- A8 (feature_certificate) sort de SS6 validate, pas de characterize : spécificité, sensibilité, sélectivité, probe. C’est le GATE G2.
- Le GATE G3 est sur l’intervention elle-même (jobs.steer), pas sur le jugement — le jugement (A9′) est une étape distincte, en aval.
- Aucun A7/A8/A9 n’existe encore dans le registre : la chaîne est correcte, pas encore exécutée.
Temps estimé : 1 min 45 s
Dévoilement / design : Révéler les six blocs de gauche à droite. Terminer sur l’étiquette d’état réel pour ancrer les décomptes vivants du registre.

## Diapositive 43

Objectif : Cadrer précisément ce que l’ablation ajoute et ce qu’elle n’ajoute pas encore.
Message clé : La nécessité est la moitié manquante de la revendication d’identité; sa spécification ne vaut pas son résultat.
À dire :
- Le mécanisme est déjà dans le code : clamper à l’échelle 0.0 revient exactement à mettre la feature à zéro.
- C’est l’élément #5 de la feuille de route, encore sans intervention_result associé dans le registre.
- Je répète explicitement : aucune ablation n’a encore été exécutée. Cette slide décrit un protocole, pas un résultat.
Temps estimé : 1 min 30 s
Dévoilement / design : Révéler les deux cartes côte à côte, puis l’étiquette de garde-fou, puis la phrase mécanisme.

## Diapositive 44

Objectif : Montrer que la comparaison informative repose sur trois bras, pas deux.
Message clé : Le contrôle de spécificité sépare « cette feature compte » de « annuler n’importe quelle feature dégrade la sortie ».
À dire :
- baseline vs steered donne la nécessité brute; steered vs random_feature donne la spécificité.
- random_direction est produit automatiquement en mode claim mais reste dégénéré à l’échelle 0 : à ignorer.
- prompt_baseline calibre le plancher du juge, indépendamment de la feature testée.
Temps estimé : 1 min 30 s
Dévoilement / design : Révéler les quatre lignes de haut en bas, puis l’étiquette grise en dernier pour ne pas la faire lire comme un cinquième bras informatif.

## Diapositive 45

Objectif : Faire comprendre pourquoi la pré-inscription protège la revendication de nécessité future.
Message clé : Un protocole pré-enregistré retire le choix a posteriori du seuil de succès.
À dire :
- bootstrap_ci et effect_size sont les primitives SS9 déjà figées (interplab/stats/stats.py), pas une méthode ad hoc.
- H2 est un test en deux parties : il faut à la fois un effet spécifique ET une équivalence du contrôle avec la baseline.
- Le verrou à trois graines interdit explicitement le retry sélectif si un seul seed échoue.
- INCONCLUSIVE est un résultat valide prévu à l’avance, pas un échec de protocole.
Temps estimé : 2 min
Dévoilement / design : Révéler H1 et H2 côte à côte en premier, puis les trois cartes basses, puis la phrase de fermeture.

## Diapositive 46

Objectif : Présenter l’infrastructure livrée avec la même rigueur que le reste de la section.
Message clé : Les trois éléments sont vérifiés sur origin/main au moment de cette diapositive, pas supposés.
À dire :
- Battery v1.1.0 : le concept fromage est researcher-authored (ED-8), status probes_only — sensitivity restera non mesurée tant qu’aucun word_absent n’est fourni, cohérent avec la limite explicite plus loin dans la section.
- Le lanceur de recensement est fusionné sur main (commit 9d90ef6).
- L’enveloppe GPU whole-node est standardisée sur les six lanceurs, fusionnée — pas seulement préparée sur une branche isolée.
- sae_certificate = 4 en registre, tous produits sous la pile 6.x post-migration.
Temps estimé : 1 min 30 s
Dévoilement / design : Révéler les trois cartes de gauche à droite, puis la phrase de synthèse.

## Diapositive 47

Objectif : Présenter le verrouillage d’environnement comme une contribution scientifique, pas seulement opérationnelle.
Message clé : Sans cette discipline, un futur certificat ne dirait rien de fiable sur quelle bibliothèque a produit ses nombres.
À dire :
- Aucune installation globale n’est permise, sur le cluster comme en local (ED-1, étendu par ED-36).
- Le virtualenv est créé --no-download puis pip/setuptools/wheel sont immédiatement remplacés par la version épinglée et vérifiée par hachage du bundle — les paquets embarqués de virtualenv ne servent que d’amorce transitoire.
- Un wheel dérivé conserve son sdist source et son hachage correspondant au lock — aucune substitution silencieuse de version n’est possible.
Temps estimé : 1 min 45 s
Dévoilement / design : Révéler les quatre cartes en grille 2×2. Prendre le temps sur « admission par wheel », le point le plus technique.

## Diapositive 48

Objectif : Fermer la section en rendant explicites toutes les limites qui empêchent un sur-claim.
Message clé : Chaque limite listée ici est vérifiée dans le code ou le registre au moment de cette diapositive, pas supposée.
À dire :
- ED-19 est la même contrainte numpy qui a mis en pause l’intégration SS8 pendant la migration ED-33 — elle n’a jamais été levée.
- Stage 1 vs Stage 2 est une distinction stricte du protocole (docs/ablation_9056_spec.md §6) : seul Stage 2, jugé par Lodestar en direct, compte comme preuve.
- Le nom exact du champ de config est judge (pas specificity_judge) — je corrige la formulation pour rester fidèle au schéma A8 réel.
- L’absence de revision FineWeb est une limite de provenance historique (ED-8), pas une erreur d’aujourd’hui — le sample_checksum en est le palliatif honnête.
Temps estimé : 2 min
Dévoilement / design : Révéler les quatre cartes en grille 2×2, dans l’ordre de lecture. Ne pas accélérer sur la dernière : c’est la garantie de traçabilité du corpus.
