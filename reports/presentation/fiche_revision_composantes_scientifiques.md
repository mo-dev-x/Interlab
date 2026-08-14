# Fiche de révision - composantes scientifiques et métriques

Source principale : `internship_report.md`  
But : te préparer aux questions du PI sur les termes, métriques et choix méthodologiques autour des slides 25-41.  
Note : je saute les bases des SAE, comme demandé, mais je garde les notions SAE-adjacentes nécessaires pour expliquer les résultats.

## 1. À dire en ouverture si on te demande "c'est quoi la logique scientifique ?"

Le projet ne se limite pas à trouver une génération intéressante. La logique scientifique est :

1. Certifier que l'instrument est utilisable.
2. Sélectionner des features candidates avec plusieurs signaux.
3. Tester le steering sur une plage d'échelles.
4. Évaluer les générations avec des rubriques explicites.
5. Choisir un point opératoire selon une règle.
6. Séparer ce qui est démontré, prudent et non démontré.

Phrase utile :

> Le résultat 9056 est fort parce qu'il est soutenu par une triangulation : santé du checkpoint, caractérisation de la feature, contrôle à taux apparié et sweep jugé par Lodestar.

## 2. Comment on trouve typiquement une feature, expliqué très simplement

Imagine que le modèle est une grosse machine qui lit une phrase mot par mot. À chaque mot, quelque part au milieu de la machine, il y a un énorme tableau de nombres. Ce tableau de nombres décrit ce que le modèle "pense" à ce moment-là. Dans ton projet, on regarde surtout ce tableau à la couche 28.

Le SAE est comme une loupe spéciale. On lui donne ce tableau de nombres, et il essaie de le traduire en petites lumières plus faciles à interpréter. Chaque lumière correspond à une feature possible. Une lumière peut correspondre à quelque chose comme fromage, UNESCO, ponctuation, langue française, noms propres, code, etc.

Le déroulement typique est :

1. On prend beaucoup de texte du corpus.
2. On fait lire ce texte au modèle.
3. À chaque token, on récupère l'activation interne du modèle à une couche donnée, par exemple la couche 28.
4. On donne cette activation au SAE.
5. Le SAE calcule l'intensité de toutes ses features.
6. Comme c'est un SAE TopK, il garde seulement les `k` features les plus actives pour ce token, ici 100.
7. On enregistre quelles features se sont allumées, à quel endroit, et avec quelle force.
8. Après beaucoup de tokens, on regarde quelles features ont des activations fortes et rares.
9. On inspecte les textes où ces features s'allument le plus.
10. On donne une hypothèse humaine à la feature : par exemple "celle-ci ressemble à fromage".

Phrase version enfant de 6 ans :

> Le modèle lit une phrase. À chaque mot, plusieurs petites lumières s'allument dans le SAE. TopK dit : "je garde seulement les 100 lumières les plus fortes". Ensuite, on regarde dans quels textes une lumière s'allume très fort pour deviner ce qu'elle veut dire.

Point très important :

TopK ne veut pas dire qu'on choisit les 100 meilleures features du modèle une fois pour toutes. TopK se passe **à chaque token**. Pour chaque token, le SAE calcule beaucoup de features possibles, puis garde seulement les 100 plus fortes à ce moment-là.

Donc il y a deux niveaux à ne pas confondre :

- **TopK interne au SAE** : pour chaque token, garder les 100 features les plus actives.
- **Feature survey** : après avoir regardé beaucoup de tokens, classer toutes les features du dictionnaire pour trouver celles qui semblent intéressantes.

Exemple concret avec fromage :

1. Le corpus contient une phrase comme "The cheese was sharp and aged."
2. Le modèle lit cette phrase.
3. À la couche 28, l'état interne du modèle contient beaucoup d'information.
4. On passe cet état dans le SAE.
5. Une feature comme 9056 peut s'allumer fortement sur des tokens ou contextes liés au fromage.
6. Si 9056 s'allume souvent dans des contextes fromage, mais pas partout, elle devient une candidate.
7. Ensuite, on la teste plus sérieusement avec caractérisation, contrôles et steering.

## 3. D'où viennent les activations données au SAE ?

Les activations viennent du modèle lui-même, pas du SAE.

Étape par étape :

1. On donne un texte au modèle.
2. Le modèle transforme le texte en tokens.
3. Le modèle fait un forward pass.
4. À une couche choisie, par exemple la couche 28, on copie le residual stream.
5. Ce residual stream est un vecteur de nombres.
6. Ce vecteur est envoyé dans l'encodeur du SAE.
7. L'encodeur du SAE produit une liste de valeurs : une valeur par feature.
8. TopK garde seulement les 100 plus grandes valeurs.

Formulation simple :

> Le SAE ne lit pas directement le texte. Le modèle lit le texte; le SAE lit l'état interne du modèle.

Autre formulation utile :

> Une feature s'active quand l'état interne du modèle ressemble à la direction apprise par cette feature.

## 4. Comment le feature survey trouve des candidates ?

Après avoir passé beaucoup de textes dans le modèle et le SAE, on a une grande table mentale :

- feature 0 : activée ici, là, là;
- feature 1 : activée ailleurs;
- feature 9056 : activée fortement dans certains contextes;
- feature 47735 : activée fortement dans d'autres contextes;
- etc.

Le survey cherche les features qui ont deux propriétés :

1. Elles ont parfois des activations très fortes.
2. Elles ne s'activent pas tout le temps.

Dans le rapport, le score de survey ressemble à :

`peak activation x (1 - nonzero fraction)`

Intuition :

- `peak activation` : est-ce que la feature s'allume très fort quelque part ?
- `nonzero fraction` : est-ce qu'elle s'allume partout ou seulement dans certains cas ?
- `(1 - nonzero fraction)` : bonus pour les features plus rares.

Version très simple :

> On cherche des lumières qui brillent très fort dans certains textes, mais qui ne sont pas allumées tout le temps.

Ensuite, pour les meilleures candidates, on regarde leurs exemples les plus activants. Si une feature s'allume surtout dans des textes parlant de cheddar, fromage, dairy, brie, etc., on peut proposer l'étiquette "fromage". Mais cette étiquette est seulement une hypothèse au début.

## 5. Comment on passe de "candidate intéressante" à "feature crédible" ?

Trouver une candidate ne suffit pas. Il faut ensuite tester si elle est vraiment propre.

Le chemin typique est :

1. **Survey** : trouver une feature qui semble intéressante.
2. **Inspection des exemples max-activants** : regarder les textes où elle s'allume le plus.
3. **Caractérisation** : mesurer firing rate, max activation, mean activation, nombre d'événements.
4. **Contrôle à taux apparié** : comparer avec une feature qui s'active aussi souvent mais ne devrait pas porter le concept.
5. **Steering sweep** : forcer la feature à différentes échelles et générer du texte.
6. **Évaluation Lodestar** : juger cohérence, pertinence conceptuelle, adhérence au prompt et naturalité.
7. **Point opératoire** : choisir une échelle avec une règle explicite.

Phrase utile :

> Une feature n'est pas crédible parce qu'elle a un joli nom; elle devient crédible quand plusieurs tests indépendants racontent la même histoire.

## 6. Comment on "active" une feature pendant le steering ?

Pendant la découverte, on observe quand une feature s'active naturellement. Pendant le steering, on force son activation.

Version simple :

1. Le modèle commence à générer une réponse.
2. À la couche choisie, on intercepte son état interne.
3. On passe cet état dans le SAE.
4. On prend la feature choisie, par exemple 9056.
5. On remplace ou fixe son activation à une valeur choisie, par exemple scale 55.
6. On reconstruit l'effet dans l'espace du modèle avec le décodeur SAE.
7. On remet l'état modifié dans le modèle.
8. Le modèle continue à générer, mais maintenant avec la feature forcée.

Version enfant de 6 ans :

> Pendant que le modèle parle, on ouvre la machine au milieu, on tourne le bouton "fromage" plus haut, puis on laisse la machine continuer à parler.

Attention :

- On ne prouve pas avec ça que la feature est nécessaire.
- On prouve seulement que forcer cette feature suffit à produire un effet.
- Pour prouver la nécessité, il faudrait faire une ablation : enlever ou bloquer la feature et voir si l'effet disparaît.

## 7. Résumé en une minute : découverte à steering

Si tu dois expliquer tout le processus rapidement :

> Je prends des textes, je les fais passer dans Qwen, puis je récupère les activations internes à la couche 28. Je passe ces activations dans le SAE. Pour chaque token, le SAE active seulement les 100 features les plus fortes, parce que c'est un TopK SAE. Ensuite, sur beaucoup de tokens, je cherche les features qui s'activent fortement mais rarement. Je regarde leurs exemples max-activants pour proposer une étiquette, comme fromage. Après ça, je ne m'arrête pas à l'étiquette : je mesure la sélectivité, je compare à des contrôles à taux apparié, je force la feature à plusieurs échelles, puis Lodestar juge les générations. C'est comme ça qu'une candidate devient un résultat défendable.

## 8. Architecture TopK

TopK signifie que, pour chaque token, seules les `k` features les plus actives sont gardées. Dans ce projet, `k = 100`.

Pourquoi c'est important :

- Le L0 est fixé par architecture. Un mauvais TopK SAE peut encore afficher 100 features actives par token.
- Donc L0 seul ne suffit pas à dire que le SAE est sain.
- C'est une raison directe pour avoir une certification avec CE récupéré, FVU et fraction de features mortes.

Formulation courte :

> TopK rend la sparsité contrôlée par design, mais ça peut masquer un instrument malade. La certification sert à regarder au-delà du L0.

## 9. L0

L0 mesure le nombre de features actives par token.

Dans un SAE TopK, L0 est essentiellement égal à `k`. Ici, il est donc autour de 100 par construction.

À ne pas dire :

- Ne pas dire que L0 prouve la santé du SAE.

À dire :

> Dans cette architecture, L0 est surtout un paramètre de design. La santé globale vient plutôt de la reconstruction, de la variance inexpliquée et des features mortes.

## 10. Expansion factor

L'expansion factor est le rapport entre la dimension du dictionnaire de features et la dimension résiduelle du modèle.

Dans le rapport :

- 16x : dictionnaire plus petit.
- 32x : dictionnaire plus large.
- 64x : dictionnaire encore plus large.

Pourquoi c'est important :

- Plus de largeur peut donner plus de capacité de séparation.
- Mais la largeur ne remplace pas la couverture du corpus.
- Exemple : doubler la largeur n'a pas produit une feature poutine propre.

Formulation courte :

> La largeur augmente la capacité du dictionnaire, mais si le concept est trop peu représenté dans le corpus, la capacité ne suffit pas.

## 11. Couche 28 et residual stream

Les expériences principales utilisent la couche 28 de Qwen2.5-14B-Instruct.

Le residual stream est l'état interne où l'intervention est appliquée. Le steering modifie cet état à une couche donnée, puis laisse le modèle continuer sa génération.

Formulation courte :

> Le steering est appliqué dans le residual stream à la couche 28, donc on modifie une représentation interne avant que les couches suivantes produisent la suite du texte.

## 12. Activation store

Un activation store est une collection d'activations extraites du modèle sur un corpus.

Pourquoi c'est important :

- C'est la matière première pour entraîner et analyser les features.
- Si l'extraction est mauvaise, tout le pipeline aval est suspect.
- Dans Interlab, le `store_manifest` A4 est conçu mais pas peuplé dans le snapshot du rapport.

Formulation courte :

> L'activation store est le pont entre corpus et SAE : il fixe quelles activations ont réellement été vues.

## 13. CE recovered

CE recovered signifie cross-entropy recovered.

Intuition :

- On compare la performance du modèle avec reconstruction SAE à la performance normale.
- Plus la valeur est proche de 1, plus le SAE préserve l'information utile pour le modèle.

Valeurs dans le rapport :

- `rwu04lpb` : 0,9884.
- Minimum dans les quatre SAEs certifiés : 0,9785.

À dire :

> CE recovered mesure à quel point la reconstruction SAE préserve le comportement prédictif du modèle. Pour `rwu04lpb`, la valeur est haute, mais la bande reste amber à cause de la lecture globale des métriques.

## 14. FVU

FVU signifie fraction of variance unexplained, ou fraction de variance inexpliquée.

Intuition :

- C'est la part de variance des activations que la reconstruction ne capture pas.
- Plus c'est bas, mieux c'est.

Valeur principale :

- `rwu04lpb` : FVU = 0,0103.

Formulation courte :

> FVU est une mesure directe d'erreur de reconstruction relative. Une FVU basse signifie que l'autoencodeur reconstruit bien la géométrie globale.

## 15. Fraction de features mortes

Une feature morte est une feature qui ne s'active jamais, ou presque jamais, sur l'échantillon de validation.

Pourquoi c'est important :

- Trop de features mortes signifie que le dictionnaire gaspille sa capacité.
- Dans le rapport, les fractions mortes sont très basses.

Valeur principale :

- `rwu04lpb` : 0,0008.
- Maximum affiché sur slide : inférieur ou égal à 0,0020.

Formulation courte :

> La faible fraction de features mortes indique que le dictionnaire est largement utilisé, mais ça ne prouve pas que chaque feature est interprétable.

## 16. Band verdict : green, amber, red

Le band verdict est un verdict de santé globale du SAE.

À comprendre :

- Green ne veut pas dire "meilleure feature".
- Amber ne veut pas dire "inutilisable".
- Le résultat principal utilise `rwu04lpb`, qui est amber.

Formulation courte :

> La bande certifie la santé de l'instrument, pas la qualité locale d'une feature. C'est pour ça que 9056 peut être forte même si son checkpoint est amber.

## 17. Feature firing rate

Le firing rate est la fréquence à laquelle une feature s'active sur un échantillon de tokens.

Pourquoi c'est important :

- Une feature trop rare donne peu de résolution statistique.
- Une feature trop fréquente risque d'être peu spécifique.
- Le rapport compare les candidates à la médiane de population.

Valeur utile :

- Médiane de population dans `characterize_lite` : 4,03e-05.

## 18. Nonzero fraction

La nonzero fraction mesure la fraction de positions où une feature est non nulle.

Dans le survey, elle intervient dans le score :

`peak activation x (1 - nonzero fraction)`

Intuition :

- On veut des features avec un pic fort, mais pas actives partout.
- La pénalité `(1 - nonzero fraction)` favorise les candidates plus rares.

## 19. Peak activation

Peak activation est la plus forte activation observée pour une feature.

Pourquoi c'est utile :

- Une feature candidate devrait avoir des contextes où elle s'active nettement.
- Mais un pic peut aussi venir d'un artefact.

Lien avec le bug :

- Avant le masking des normes aberrantes, un seul contexte artefactuel dominait le top-30.

## 20. Outlier-norm masking

Fix méthodologique important.

Le problème :

- Certains tokens avaient une norme L2 beaucoup plus grande que le reste de la séquence.
- Ces positions faisaient monter artificiellement beaucoup de features dans le ranking.
- Avant la correction, 27 des 30 premières candidates venaient d'un même contexte artefactuel sur la Coupe du monde 2018.

La correction :

- Masquer les positions où `norme activation > 4 x norme médiane de la séquence`.

Pourquoi c'est important :

> Les candidates fromage, UNESCO et Eurovision émergent proprement seulement après ce masking.

## 21. Concept probing

Méthode initiale de découverte de features.

Principe :

- On définit un concept à l'avance.
- On compare des probes conceptuelles à des probes générales.
- On classe les features selon un signal de spécificité.

Limite :

- Elle dépend de concepts définis à l'avance.
- Elle a été remplacée ou dépriorisée par le survey ouvert.

## 22. Open-ended feature survey

Méthode plus ouverte utilisée pour trouver les candidates principales.

Principe :

- Classer toutes les features d'un checkpoint.
- Utiliser un score du type `peak activation x (1 - nonzero fraction)`.
- Examiner les candidates les plus saillantes.

Garde-fou :

- Le fichier complet du job 358227 n'a pas été retrouvé localement.
- Le rapport traite seulement les candidates ensuite vérifiées par caractérisation et steering.

## 23. characterize_lite

Script ad hoc de caractérisation.

Ce qu'il mesure :

- firing rate;
- max activation;
- mean activation;
- nombre d'événements de firing;
- comparaison avec un contrôle à taux apparié.

Garde-fou :

> `characterize_lite` est une preuve suffisante pour le rapport, mais pas un certificat Interlab A7/A8 complet.

## 24. Contrôle à taux apparié

Un contrôle à taux apparié est une feature qui s'active à une fréquence comparable à la candidate, mais qui ne devrait pas porter le même concept.

Pourquoi c'est important :

- Il évite de confondre rareté et qualité.
- Si la candidate ne dépasse pas son contrôle, elle est faible.

Exemple :

- 44189 Eurovision est rejetée notamment parce qu'elle est sous son contrôle à taux apparié.

## 25. Specificity, sensitivity, selectivity

Ces termes apparaissent surtout dans l'architecture Interlab cible pour le futur Gate G2.

Intuition :

- Specificity : la feature s'active pour le concept cible.
- Sensitivity : elle ne s'active pas trop pour les contrôles non liés.
- Selectivity : elle capture le concept, pas seulement un mot littéral.

Garde-fou :

- Dans le projet actuel, A8 `feature_certificate` est conçu mais non peuplé.
- Donc ne pas présenter ces métriques comme déjà certifiées pour 9056 dans Interlab.

## 26. Specificity-ratio epsilon floor

Bug ou piège méthodologique identifié.

Le problème :

- Un ratio comme `mean_poutine / (mean_general + 1e-8)` explose si le dénominateur est presque zéro.
- Avec TopK, beaucoup de features ont exactement zéro activation hors top-k.
- On peut obtenir des ratios énormes mais sans signification.

Correction pratique :

- Rapporter les activations moyennes brutes plutôt que des ratios trompeurs dans ce cas.

## 27. Feature steering

Principe :

- Choisir une feature.
- Fixer ou modifier son activation pendant la génération.
- Observer si le comportement du modèle change dans la direction du concept.

Dans le rapport :

- Steering par hook encode-override-decode.
- Scales typiques : 40 à 150.
- Feature principale : 9056, concept fromage.

## 28. Clamping

Clamping signifie fixer l'activation d'une feature à une valeur ou échelle choisie pendant la génération.

Formulation courte :

> Au lieu d'attendre que la feature s'active naturellement, on force son activation et on observe l'effet causal suffisant sur le texte généré.

## 29. Steering scale

L'échelle de steering contrôle l'intensité de l'intervention.

Pourquoi c'est important :

- Trop bas : l'effet conceptuel est faible.
- Trop haut : la cohérence peut chuter ou la génération peut dégénérer.

Exemple 9056 :

- Scale 40 : cohérence 6,50, pertinence 2,63.
- Scale 55 : cohérence 5,38, pertinence 5,50.
- Scale 60 : cohérence 4,50, pertinence 7,75, donc sous le plancher de cohérence.

## 30. Point opératoire

Un point opératoire est l'échelle retenue pour défendre un résultat.

Dans le rapport :

- Règle : maximiser la pertinence conceptuelle sous contrainte de cohérence.
- Contrainte utilisée : cohérence au moins 5.
- Point retenu pour 9056 : scale 55.

Formulation courte :

> Le point opératoire n'est pas le maximum de fromage; c'est le meilleur compromis défini avant l'interprétation.

## 31. Suffisance vs nécessité

Suffisance :

- Activer la feature produit l'effet.
- C'est ce qui est montré pour 9056.

Nécessité :

- Retirer ou ablater la feature fait disparaître l'effet.
- Ce n'est pas encore démontré.

Phrase très importante :

> 9056 est une démonstration de suffisance, pas encore de nécessité.

## 32. Ablation

Une ablation consiste à retirer, bloquer ou neutraliser une composante pour tester si l'effet disparaît.

Pourquoi c'est la priorité :

- Elle transformerait le résultat 9056 d'une preuve de suffisance en test de nécessité.
- C'est le garde-fou causal principal du rapport.

## 33. Delta-form steering

Delta-form signifie que l'intervention ajoute une modification au residual stream plutôt que de remplacer brutalement l'état interne.

Pourquoi c'est important :

- Remplacer la reconstruction peut introduire un artefact.
- Ajouter un delta est plus propre comme intervention.
- Le rapport mentionne qu'un bug de steering antérieur venait de copies divergentes de hooks.

## 34. Identity test ou no-op test

Test de sanity check pour les hooks.

Principe :

- Si l'échelle de steering est zéro, la sortie devrait être identique ou équivalente à la baseline.
- Si ce n'est pas le cas, le hook modifie le modèle même sans intervention réelle.

Dans Interlab :

- Gate G3 teste ce type de propriété pour le moteur d'intervention.
- Le moteur SS7 est implémenté comme trunk, mais A9 n'est pas peuplé dans le registre.

## 35. Golden delta test

Test de référence pour vérifier que l'intervention produit le même delta attendu sur un prompt fixe.

Pourquoi c'est important :

- Il protège contre des changements silencieux dans les kernels, versions ou hooks.
- Le rapport mentionne une tolérance ULP ajustée après migration de version.

## 36. ULP tolerance

ULP signifie unit in the last place.

Intuition :

- C'est une mesure très fine de différence numérique entre deux flottants.
- Elle sert à tolérer de petites différences de calcul entre versions ou plateformes.

Dans le rapport :

- Tolérance ordinaire : MAX_ULP 32.
- Après migration liée à `sae-lens` 6.x : MAX_ULP 128 pour le golden delta.

## 37. Lodestar

Lodestar est la plateforme d'évaluation jugée.

Rôle :

- Ingestion des `generations.json`.
- Estimation de coût.
- Jugement LLM avec rubriques.
- Cache SQLite content-addressed.
- Frontière cohérence-pertinence.
- Recherche de point opératoire.
- Rapport HTML autonome.

À dire clairement :

> Lodestar a été réellement exercé pour les résultats de Section 3, mais en mode autonome, pas encore comme A9/A11 dans Interlab.

## 38. LLM-as-judge

Un LLM-as-judge est un modèle utilisé pour noter des sorties textuelles selon des rubriques.

Dans le rapport :

- Juge : Claude Sonnet 4.5.
- Trois jugements répétés par génération.

Garde-fou :

- Self-consistency élevée ne prouve pas accord humain.
- Pas d'étude de corrélation avec des annotateurs humains.

## 39. Rubrique : coherence

Mesure si le texte est grammatical, lisible, non dégénéré et globalement compréhensible.

Dans les slides :

- Le seuil de cohérence utilisé pour 9056 est au moins 5.
- Scale 55 garde 5,38.

## 40. Rubrique : concept relevance

Mesure à quel point la génération manifeste le concept cible.

Pour 9056 :

- Scale 55 : 5,50.
- Les échelles plus hautes peuvent avoir une pertinence plus forte, mais avec une cohérence plus faible.

## 41. Rubrique : prompt adherence

Mesure si le modèle répond encore à la consigne initiale.

Pourquoi c'est important :

- Une feature peut imposer un concept mais faire oublier la question.
- UNESCO illustre ce risque : pertinence forte, intégration et adhérence plus faibles.

Valeur 9056 :

- Prompt adherence : 3,13.

## 42. Rubrique : integration naturalness

Mesure si le concept est intégré naturellement dans la réponse plutôt que plaqué artificiellement.

Valeur 9056 :

- Integration naturalness : 1,75.

Interprétation :

- L'effet est réel mais pas parfaitement naturel.
- Ça évite de vendre le résultat comme une génération normale.

## 43. Literal mention

Rubrique ou signal complémentaire qui vérifie si le concept est mentionné littéralement.

Pourquoi ce n'est pas suffisant :

- Mentionner "cheese" ne veut pas dire que la réponse est cohérente.
- Une métrique de grep ne remplace pas les rubriques comportementales.

## 44. Degeneration flags

Détection de comportements dégénérés :

- répétitions;
- topic salad;
- dérive de langue;
- gibberish;
- syntaxe cassée.

Pourquoi c'est important :

- À haute échelle, une génération peut devenir très conceptuelle mais inutilisable.

## 45. Krippendorff alpha

Krippendorff alpha mesure l'accord ou la cohérence entre jugements répétés.

Dans le rapport :

- Chaque génération est jugée trois fois.
- Alpha est au moins 0,91 sur toutes les rubriques dans les six runs standard.

Interprétation :

- Haut alpha : accord quasi déterministe entre répétitions, à réglages fixes (le juge tourne à température 0) — un contrôle de déterminisme, pas une preuve que le juge est stable ou fiable.
- Ce n'est pas une preuve d'accord avec des humains.

Phrase utile :

> Le juge fonctionne à température 0. Krippendorff alpha mesure donc un accord quasi déterministe entre répétitions à réglages fixes — un contrôle de déterminisme, et non la fiabilité, la stabilité ou une répétabilité validée du juge.

## 46. ICC

ICC signifie intraclass correlation coefficient.

Rôle :

- Mesure, sous réglages fixes et à température 0, un accord quasi déterministe des scores numériques entre répétitions — un contrôle de déterminisme, pas une preuve de stabilité ou de fiabilité.
- Utile pour des rubriques ordinales ou continues comme cohérence et pertinence.

À dire simplement :

> ICC complète alpha pour vérifier que les scores répétés varient peu.

## 47. Fleiss kappa

Fleiss kappa mesure l'accord sur des décisions catégorielles ou binaires.

Dans le rapport :

- Utilisé pour la rubrique binaire.

À dire :

> Fleiss kappa est utile quand la sortie n'est pas un score ordinal mais une décision de type oui/non ou catégorie.

## 48. Human-correlation validation

Validation absente dans le rapport.

Ce que ce serait :

- Comparer les jugements Lodestar à des annotations humaines.
- Mesurer si le LLM judge correspond aux humains.

À dire :

> Le rapport mesure la cohérence interne du juge, pas encore sa validité humaine.

## 49. Mock judge

Le rapport exclut un artefact important :

- `lodestar_montreal_golden_gate` contient des jugements `mock-deterministic-v1`.
- Ce sont des placeholders de test, pas de vrais jugements LLM.

Conséquence :

- Ne pas citer ces statistiques comme preuve de fiabilité du juge.
- Pas de fiabilité réelle mesurée pour le texte extrême très dégénéré.

## 50. Coherence-relevance frontier

Frontière qui met en relation :

- cohérence;
- pertinence conceptuelle;
- échelle de steering.

Pourquoi c'est central :

- Elle permet de choisir une échelle par règle.
- Elle remplace l'inspection à l'oeil.

Phrase utile :

> La frontière transforme le sweep en décision expérimentale.

## 51. Optimal operating point search

Recherche automatique du meilleur point sous contrainte.

Dans le rapport :

- Objectif : maximiser concept relevance.
- Contrainte : coherence au moins 5.
- Résultat 9056 : scale 55.

## 52. Steering Efficacy Score

Métrique composite implémentée dans Lodestar.

Intuition :

- Combine pertinence et cohérence pour résumer l'efficacité d'une intervention.

Garde-fou :

- Le rapport dit que les résultats de Section 3 reposent surtout sur frontière et point opératoire, pas nécessairement sur cette métrique composite.

## 53. Control gap

Le control gap compare l'effet de la feature cible à un contrôle.

Pourquoi c'est important :

- Il teste si le comportement vient vraiment de la feature cible plutôt que d'un effet générique du steering.

Garde-fou :

- Implémenté dans Lodestar, mais pas la métrique principale utilisée pour porter les résultats de Section 3.

## 54. Bootstrap confidence interval

Un intervalle de confiance bootstrap est obtenu en rééchantillonnant les données.

Rôle :

- Estimer l'incertitude sans supposer une distribution paramétrique simple.
- Lodestar inclut des IC bootstrap à 95 % pour certains metrics comme control gap.

## 55. Mann-Whitney U

Test statistique non paramétrique.

Rôle :

- Comparer deux distributions, par exemple une condition steered et un contrôle.
- N'exige pas une normalité stricte.

Garde-fou :

- Mentionné comme métrique implémentée, pas comme argument central des résultats principaux.

## 56. SQLite cache content-addressed

Lodestar cache les jugements avec une clé incluant :

- texte;
- rubrique;
- modèle juge;
- nombre de répétitions.

Pourquoi c'est important :

- Évite de repayer des jugements identiques.
- Permet de régénérer un rapport après correction analytique.

Exemple :

- Après le bug `sweep_hash`, le rapport a pu être régénéré à coût zéro.

## 57. estimate et budget

Fonctionnalités Lodestar pour borner les coûts.

Rôle :

- Estimer le coût d'un run avant exécution.
- Refuser un run qui dépasse le budget.

Pourquoi c'est scientifique :

- Permet des campagnes reproductibles et planifiables.
- Évite de choisir les évaluations seulement selon l'intuition du moment.

## 58. HTML report

Rapport Lodestar autonome.

Contenu typique :

- overview;
- frontier;
- optimal operating points;
- control gap;
- judge validation;
- generations;
- export.

Pourquoi c'est important :

- C'est l'interface de revue scientifique.
- Le bug `sweep_hash` a été repéré en lisant ce rapport.

## 59. Bug FFFD

Problème :

- `tokenizer.decode()` pouvait produire le caractère de remplacement Unicode `�`.
- Le juge recevait du texte corrompu et pouvait donner un score plancher.

Impact :

- 97 jugements sur 1872 affectés, soit environ 5 %.
- Concentration forte à scale 80.

Correction :

- Supprimer `�` dans `generate_text()`.

## 60. Bug sweep_hash

Problème :

- Le `sweep_hash` excluait le paramètre scale pour grouper les sweeps.
- Une condition d'ablation scale 0 était mélangée à la frontière de steering.

Correction :

- Ajouter une colonne `experiment`.
- Grouper par `experiment` en plus de `sweep_hash`.

Phrase importante :

> Ce bug concernait le groupement analytique, pas la fiabilité intrinsèque du juge.

## 61. Chat-template gap

Problème :

- Les scripts base-model ne passaient pas toujours par `tokenizer.apply_chat_template()`.
- Le modèle pouvait continuer un texte brut au lieu de répondre comme assistant.

Correction :

- Ajouter un flag `--chat_template`.

Importance :

- Un mauvais format de prompt peut être confondu avec une mauvaise feature.

## 62. Dataset-loading obstacles

Trois obstacles importants :

- `monology/pile-uncopyrighted` bloqué par `trust_remote_code`.
- FineWeb non-streaming essayait de résoudre un nombre massif de shards.
- Les noeuds Tamia n'avaient pas d'accès internet direct.

Pourquoi c'est pertinent :

- Le passage de pile-10k à FineWeb est un workaround technique, pas un choix scientifique libre.

## 63. SAE dtype cascade bug

Même si tu connais les SAE, ce bug peut être demandé.

Problème :

- Le buffer d'activations pouvait défauter en float32.
- Des SAEs bfloat16 causaient un mismatch pendant le backward.
- Certaines configs étaient silencieusement perdues.

Correction :

- Cast explicite vers `sae.dtype`.
- Wiring explicite de `dtype`, `output_path` et logger.
- Smoke tests avant jobs longs.

## 64. Multilingual top-20 overlap

Méthode :

- Pour chaque concept et langue, prendre les 20 features les plus activées.
- Comparer les ensembles par chevauchement.

Concepts :

- world_cup;
- quebec;
- poutine;
- couscous.

Langues :

- anglais;
- français;
- chinois;
- arabe.

Garde-fou :

> Top-20 overlap ne prouve pas l'existence d'une feature unique.

## 65. Comment lire les matrices multilingues

La figure multilingue contient une petite matrice par concept :

- une matrice pour poutine;
- une matrice pour world_cup;
- une matrice pour couscous;
- une matrice pour quebec.

Chaque matrice répond à la question :

> Pour ce concept, est-ce que les langues utilisent les mêmes features principales ?

### Version très simple

Imagine que chaque langue a une boîte de 20 cartes.

- La boîte anglais contient les 20 features les plus actives pour le concept.
- La boîte français contient les 20 features les plus actives pour le même concept.
- La boîte chinois contient ses 20 features.
- La boîte arabe contient ses 20 features.

La matrice compare les boîtes deux par deux.

Si deux langues ont beaucoup de cartes en commun, la case est claire/jaune et le nombre est haut.  
Si deux langues ont peu de cartes en commun, la case est foncée/violette et le nombre est bas.

### Ce que sont les lignes et les colonnes

Les lignes et les colonnes sont les langues :

- `en` : anglais;
- `fr` : français;
- `zh` : chinois;
- `ar` : arabe.

Une case se lit comme :

> ligne contre colonne.

Par exemple, dans la matrice poutine :

- la case `en` contre `fr` compare les top-20 features poutine en anglais avec les top-20 features poutine en français;
- la case `fr` contre `ar` compare les top-20 français avec les top-20 arabes;
- la diagonale `en/en`, `fr/fr`, `zh/zh`, `ar/ar` vaut toujours 1,00 parce qu'une langue est parfaitement identique à elle-même.

La matrice est symétrique :

- `en/fr` donne la même information que `fr/en`;
- donc tu peux lire seulement la moitié de la matrice.

### Ce que signifie une valeur de Jaccard

Chaque langue a un ensemble de 20 features.  
Jaccard compare deux ensembles :

`Jaccard = intersection / union`

Exemple jouet avec 5 features au lieu de 20 :

- anglais : `{1, 2, 3, 4, 5}`;
- français : `{1, 2, 3, 6, 7}`;
- intersection : `{1, 2, 3}`, donc 3 features en commun;
- union : `{1, 2, 3, 4, 5, 6, 7}`, donc 7 features au total;
- Jaccard = 3/7 = 0,43.

Donc une valeur de 0,60 ne veut pas dire "60 % de probabilité".  
Ça veut dire que les deux ensembles de features se chevauchent fortement selon la formule intersection/union.

### Différence entre le titre "shared 10/20" et les cases

Le titre au-dessus de chaque matrice, par exemple :

- `poutine shared 10/20`;
- `world_cup shared 13/20`;
- `couscous shared 4/20`;
- `quebec shared 12/20`;

ne se lit pas comme une case de la matrice.

Ce titre indique combien de features sont partagées par les quatre langues dans leurs top-20.  
Donc `poutine shared 10/20` veut dire :

> Sur les 20 features principales, 10 apparaissent dans les top-20 des quatre langues.

Les cases, elles, sont des comparaisons par paire de langues.  
Par exemple `en/fr = 0,60` compare seulement anglais et français.

### Comment lire chaque concept

**world_cup**  
C'est le concept le plus global dans cette figure. Le titre indique `shared 13/20`, et les cases sont généralement hautes, entre 0,60 et 0,82. Ça veut dire que les langues activent des ensembles de features très similaires pour ce concept.

Phrase à dire :

> World Cup semble représenté par un voisinage de features très partagé entre langues.

**quebec**  
Le titre indique `shared 12/20`. Les valeurs sont assez hautes, souvent autour de 0,60 à 0,74, mais certaines comparaisons avec l'arabe sont plus basses. Ça suggère un voisinage multilingue relativement partagé, mais pas parfaitement identique.

Garde-fou :

> Ce résultat ne prouve pas une feature Québec propre; il indique seulement un chevauchement d'ensembles de features.

**poutine**  
Le titre indique `shared 10/20`, et le Jaccard moyen du rapport est 0,51. C'est un chevauchement modéré.

Point crucial :

> Poutine peut avoir un voisinage de features partagé entre langues sans avoir une seule feature poutine monosemantique.

Donc ça ne contredit pas le résultat négatif :

- pas de clean poutine feature trouvée après 16+ tentatives;
- mais des ensembles de features poutine-adjacents se chevauchent quand même entre langues.

**couscous**  
Le titre indique `shared 4/20`, et les comparaisons avec l'arabe sont très basses, autour de 0,14 à 0,18. Ça veut dire que le voisinage de features pour couscous est beaucoup moins partagé entre toutes les langues, surtout avec l'arabe.

Phrase à dire :

> Couscous est le cas où les langues semblent utiliser les ensembles de features les moins alignés dans cette analyse.

### Comment présenter la conclusion

Conclusion défendable :

> Les matrices mesurent la similarité entre ensembles de features top-20 à travers les langues. Elles suggèrent un ordre qualitatif de globalité : world_cup > quebec > poutine > couscous.

Ce qu'il ne faut pas dire :

- Ne pas dire que chaque concept a une feature unique.
- Ne pas dire que poutine est résolu.
- Ne pas dire que Jaccard mesure la fréquence du concept dans le corpus.
- Ne pas dire que cette analyse prouve une loi générale sur toutes les langues.

Formulation très propre pour le PI :

> Pour chaque concept et chaque langue, je prends les 20 features les plus activées. La matrice compare ces ensembles deux par deux avec Jaccard. Donc une case haute veut dire que deux langues utilisent un voisinage de features similaire. Ce n'est pas une preuve qu'une seule feature monosemantique existe.

## 66. Jaccard overlap

Jaccard = taille de l'intersection divisée par taille de l'union.

Intuition :

- Si deux langues activent les mêmes features pour un concept, Jaccard augmente.
- Si elles activent des ensembles différents, Jaccard diminue.

À dire :

> Poutine peut avoir un chevauchement de voisinage sans avoir une feature poutine monosemantique.

## 67. BOS token excluded

BOS signifie beginning-of-sequence token.

Pourquoi exclure :

- Le token de début peut créer des activations structurelles non liées au concept.
- L'exclure réduit les artefacts dans l'analyse multilingue.

## 68. Triangulation

Triangulation = plusieurs mesures indépendantes convergent.

Ici :

- survey / caractérisation;
- steering jugé;
- contrôle à taux apparié.

Résultat :

- 9056 > 47735 > 44189.

Pourquoi c'est fort :

- Le résultat ne dépend pas d'un seul instrument.
- La méthode peut aussi rejeter une candidate faible.

## 69. Feature 9056

Concept : fromage.

Statut :

- Résultat principal.
- Instruct-model SAE `rwu04lpb`, couche 28.
- Scale retenu : 55.

Scores :

- cohérence : 5,38;
- pertinence conceptuelle : 5,50;
- prompt adherence : 3,13;
- integration naturalness : 1,75.

Claim exact :

> 9056 suffit à induire un effet d'identité conceptuelle, mais sa nécessité n'est pas démontrée.

## 70. Feature 47735

Concept : UNESCO.

Statut :

- Candidate intéressante.
- Pertinence conceptuelle possible.
- Moins bien intégrée au prompt que 9056.

Rôle scientifique :

- Contraste utile : pertinence seule ne suffit pas.

## 71. Feature 44189

Concept : Eurovision.

Statut :

- Candidate rejetée proprement.
- Faible en caractérisation.
- Faible contre contrôle à taux apparié.
- Faible en steering jugé.

Rôle scientifique :

> Montre que la méthodologie est falsifiable.

## 72. Poutine negative result

Résultat :

- Plus de 16 tentatives.
- Deux checkpoints.
- Pas de feature poutine propre.

Interprétation :

- Couverture du corpus probablement limitante.
- La largeur du dictionnaire ne compense pas une faible présence du concept.

Garde-fou :

- L'argument corpus est plausible, mais un census complet reste à faire.

## 73. Montréal / Québec entanglement

Résultat :

- Ce qui semblait être une feature Montréal/Québec propre a été corrigé comme enchevêtrement bilingue.

Pourquoi c'est important :

- Le projet a corrigé son propre positif initial.
- Ça augmente la crédibilité du reste.

## 74. Base to instruct non-transfer

Résultat :

- Une feature base-model, 19815 singing, ne s'est pas transférée proprement à l'instruct model.

Interprétation :

- L'instruction tuning réorganise suffisamment la géométrie résiduelle pour qu'on ne puisse pas supposer le transfert.

Garde-fou :

- Un seul cas, donc résultat méthodologique prudent.

## 75. High-scale fluency failure

Résultat :

- Sur Montréal enchevêtré, la fluence casse avant un régime stable obsédé mais lisible.

À ne pas généraliser :

- Ce n'est pas montré pour 9056.
- C'est une limite observée sur une feature enchevêtrée.

## 76. Evidence ledger

Le rapport classe les revendications par niveau de confiance.

À connaître :

- 9056 sufficiency : HIGH.
- Triangulation ranking : HIGH.
- Eurovision rejected : MEDIUM.
- Poutine no clean feature : HIGH.
- Multilingual concept-globality : MEDIUM.
- Necessity of 9056 : ABSENT.

Pourquoi c'est utile :

> Tu peux répondre au PI en termes de force de preuve, pas seulement en termes de résultats.

## 77. Interlab content-addressing

Content-addressing signifie qu'un artefact est identifié par son hash de contenu.

Pourquoi c'est important :

- Un chemin de fichier peut changer.
- Un hash change si le contenu change.
- Les résultats peuvent citer des artefacts exacts.

Exemple :

- Certificat `rwu04lpb` : `0a572198764d`.

## 78. RunCard

Une RunCard est un artefact de provenance d'exécution.

Rôle :

- Enregistrer qu'un job a réellement terminé.
- Capturer config, timestamp et contexte.
- Rendre l'absence de carte informative.

## 79. Fail-closed version gate

Principe :

- Si la version logicielle ne correspond pas au baseline certifié, le job échoue.

Dans le rapport :

- ED-32/ED-33 ont corrigé une mauvaise supposition : baseline initial noté 3.23.0, mais checkpoints en fait sous `sae-lens` 6.44.2.

Pourquoi c'est important :

> Une mauvaise version logicielle sous les métriques peut invalider toute la chaîne.

## 80. A1 à A12, version courte

- A1 `corpus_manifest` : flux de données consommé.
- A2 `concept_battery` : probes conceptuelles.
- A3 `census_report` : fréquence des concepts.
- A4 `store_manifest` : QA des activations.
- A5 `sae_checkpoint` : identité poids + config.
- A6 `sae_certificate` : Gate G1, santé du SAE.
- A7 `characterization_manifest` : index de features.
- A8 `feature_certificate` : Gate G2, feature validée.
- A9 `intervention_result` : générations + scores.
- A10 `run_card` : provenance d'un job.
- A11 `claim_report` : revendication assemblée.
- A12 `eval_compat_map` : compatibilité juge/rubrique/prompt.

État réel :

- Peuplés : A1, A3, A5, A6, A10.
- Conçus ou partiels : A4, A7, A8, A9, A11, A12 selon le rapport.

## 81. G1 à G4, version courte

- G1 : santé du checkpoint SAE.
- G2 : validation d'une feature.
- G3 : intervention propre.
- G4 : revendication comportementale jugée et assemblée.

État réel :

- G1 est vivant.
- G2/G3/G4 sont architecture cible dans Interlab, mais pas encore une chaîne complète peuplée.
- Lodestar donne bien les jugements comportementaux en autonome.

## 82. Phrases de sécurité à mémoriser

1. "Je présente cette chaîne comme architecture cible, pas comme claim report déjà certifié."
2. "9056 est une preuve de suffisance, pas encore de nécessité."
3. "Lodestar est self-consistent dans les runs testés, mais pas validé contre des humains."
4. "Le statut amber de `rwu04lpb` concerne la santé globale, pas la qualité locale de 9056."
5. "Le top-20 multilingue mesure un voisinage de features, pas une feature unique."
6. "`characterize_lite` soutient le rapport, mais n'est pas encore un certificat Interlab complet."
7. "Les négatifs ne sont pas des échecs isolés; ils identifient des limites de corpus, d'enchevêtrement, de géométrie instruct et d'échelle."
