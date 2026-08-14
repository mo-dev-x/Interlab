# Script oral détaillé — Présentation de progrès SAE

Source principale : `internship_report.md`  
Présentation associée : `sae_interlab_explained.pptx`, diapositives 25 à 41  
Version : script oral détaillé, en français, adapté à une rencontre de progrès où le PI ne connaît pas encore Interlab et Lodestar.

## Comment utiliser ce script

Les diapositives restent volontairement concises. Le rôle de ce document est de donner la profondeur orale qui manque volontairement aux slides : architecture, logique expérimentale, limites et décisions de recherche.

Tu peux lire ce script une ou deux fois pour t'approprier les formulations, mais en présentation il vaut mieux parler naturellement. Les phrases sont écrites comme un texte prononçable, pas comme des notes télégraphiques. Pour les diapositives Interlab et Lodestar, j'ai prévu plus de temps que dans la première version des notes, parce que ton PI aura besoin de comprendre ce que tu as réellement construit.

Durée totale réaliste avec cette version détaillée : environ 32 à 37 minutes, selon le nombre de questions.  
Durée courte possible : environ 26 minutes si tu compresses les sections "architecture" et "questions probables".

## Fil conducteur général

La phrase qui résume toute la présentation est :

> Depuis la dernière rencontre, le projet est passé d'une exploration de steering à une chaîne expérimentale instrumentée, où les checkpoints, les features, les interventions et les revendications peuvent être reliés à des artefacts, des métriques et des limites explicites.

Le récit n'est donc pas : "j'ai fait Interlab, puis Lodestar, puis des expériences".  
Le récit est plutôt :

1. Il fallait rendre les résultats plus crédibles et plus auditables.
2. Interlab répond à la question de provenance : d'où viennent les artefacts et que peut-on certifier ?
3. Lodestar répond à la question d'évaluation : comment choisir un point opératoire sans juger à l'oeil ?
4. Ces deux infrastructures rendent le résultat 9056 plus défendable.
5. Les résultats négatifs ne sont pas des échecs : ils définissent les limites actuelles et les prochaines expériences.

---

## Diapositive 25 — Depuis la dernière rencontre

Temps visé : 45 secondes

Objectif oral : ouvrir la nouvelle section comme un suivi de recherche, sans refaire l'introduction générale du projet.

Message clé : la valeur produite depuis la dernière rencontre n'est pas seulement un résultat de steering, mais une chaîne de preuve plus mature.

Script :

Le point central aujourd'hui, c'est que j'ai changé de méthodologie. Au départ, on était surtout dans une logique d'exploration : entraîner des SAE, chercher des features intéressantes, essayer de les activer et regarder ce qui sort.

Depuis, j'ai pris votre conseil et j'ai travaillé sur quelque chose de plus structurant : rendre cette exploration défendable comme expérience scientifique. C'est pour ça que les quatre mots sur la slide sont importants. Interlab apporte la partie provenance et certification. Lodestar apporte l'évaluation comportementale jugée. La feature 9056 est le résultat positif principal. Et les limites explicites évitent de transformer un bon résultat en revendication trop forte.

Donc la question à laquelle je veux répondre aujourd'hui est : qu'est-ce qui est maintenant construit, mesuré, certifié ou au contraire explicitement non démontré ?

Transition :

Je vais d'abord donner le résumé des avancées, puis je vais passer plus lentement sur Interlab et Lodestar, parce que ce sont les deux contributions d'ingénierie qui rendent les résultats scientifiques interprétables.

---

## Diapositive 26 — Trois avancées qui changent le statut du projet

Temps visé : 1 minute 15 secondes

Objectif oral : donner la vue d'ensemble avant d'entrer dans les détails.

Message clé : les contributions d'ingénierie et les contributions scientifiques se renforcent mutuellement.

Script :

Le progrès principal est double. Il y a évidemment un progrès scientifique, avec la reproduction quantitative d'un effet de type Golden Gate Claude sur Qwen2.5-14B-Instruct. Mais ce résultat est beaucoup plus intéressant parce qu'il s'inscrit maintenant dans une infrastructure d'expérience.

Première avancée : Interlab. L'idée d'Interlab est de donner une identité vérifiable aux objets du projet. Un checkpoint, une certification, un manifeste de corpus ou une carte de run ne sont plus seulement des fichiers dans un dossier. Ils deviennent des artefacts enregistrés, identifiés par leur contenu, et utilisables dans une chaîne de preuve.

Deuxième avancée : Lodestar. Lodestar remplace l'évaluation à l'oeil par des jugements structurés. Au lieu de dire "cette génération semble bonne à l'échelle 60", on peut regarder une frontière cohérence-pertinence, appliquer une contrainte de cohérence et choisir un point opératoire.

Troisième avancée : le résultat 9056. C'est la feature qui donne l'effet d'identité conceptuelle le plus propre dans ce rapport. Mais je vais le présenter en gardant la limite importante : c'est une preuve de suffisance, pas encore une preuve de nécessité.

Transition :

Pour comprendre pourquoi ces résultats sont plus crédibles qu'une simple collection d'exemples, il faut voir la chaîne expérimentale complète.

---

## Diapositive 27 — La chaîne expérimentale est maintenant instrumentée

Temps visé : 2 minutes

Objectif oral : expliquer le pipeline comme une structure de preuve, pas comme une liste de scripts.

Message clé : chaque étape du travail a maintenant un rôle défini dans la production, l'évaluation ou la certification des résultats.

Script :

Cette slide montre la chaîne complète en neuf étapes. L'objectif n'est pas de détailler chaque script ligne par ligne, mais de montrer que l'expérience n'est plus seulement une suite de manipulations manuelles.

La première partie concerne la production de l'instrument : on entraîne un SAE sur les activations du modèle, puis on vérifie la qualité de l'activation store, et surtout on certifie le SAE. Cette certification est importante parce qu'elle répond à une question très simple : est-ce que l'instrument sur lequel je vais chercher des features est suffisamment sain pour être utilisé ?

Ensuite vient la partie découverte et caractérisation. On a d'abord utilisé une approche par concepts, avec des probes ciblées, puis une approche plus ouverte avec `survey_features.py`, qui classe les features sans présupposer à l'avance le concept recherché. Les candidates importantes du rapport, comme fromage, UNESCO et Eurovision, viennent de cette logique de survey.

Après ça, on passe à l'intervention : on fixe l'activation d'une feature SAE à une certaine échelle pendant la génération. C'est le steering. Mais une génération seule n'est pas une mesure. C'est là que Lodestar intervient : il prend les générations, les juge selon des rubriques, construit une frontière cohérence-pertinence et aide à choisir l'échelle.

Enfin, il y a l'analyse multilingue et l'assemblage du rapport. Interlab est la couche qui donne une identité aux artefacts de cette chaîne. Lodestar est la couche qui transforme les sorties de steering en résultats évalués.

La nuance importante est celle-ci : Interlab est vivant jusqu'au jalon de certification G1, avec des artefacts réels A1, A3, A5, A6 et A10. Lodestar, lui, a été exercé de manière autonome pour les évaluations rapportées ici. L'intégration complète où les résultats Lodestar deviennent des artefacts A9 puis A11 dans Interlab est conçue, mais pas encore peuplée.

Transition :

Avant de parler des features, je veux expliquer pourquoi la certification des SAE était nécessaire.

---

## Diapositive 29 — Interlab : frontière actuelle au jalon G1

Temps visé : 5 minutes

Objectif oral : expliquer Interlab en profondeur : problème, architecture, artefacts, philosophie et état réel d'implémentation.

Message clé : Interlab est une architecture de laboratoire pour la provenance et la certification, pas une simple librairie utilitaire.

Script :

Interlab est probablement la partie que je dois expliquer le plus clairement. En une phrase, Interlab est une architecture de laboratoire pour rendre les expériences SAE reproductibles, certifiables et auditables. Ce n'est pas seulement un dossier de scripts. C'est une manière de définir quels objets existent dans l'expérience, comment ils sont identifiés, quels certificats ils doivent porter, et quelles revendications on a le droit de faire à partir d'eux.

Le rapport explique que cette infrastructure est née de trois problèmes très concrets.

Premier problème : les échecs silencieux de santé SAE. Avant la certification, on pouvait chercher des features sur un checkpoint sans savoir si l'instrument était suffisamment sain. Avec TopK, c'est particulièrement dangereux parce que le L0 fixe peut masquer un SAE sous-entraîné.

Deuxième problème : les dérivations de features n'étaient pas comparables. Plusieurs scripts avaient leur propre copie des hooks de steering ou des probes. Quand un bug de steering est copié d'un script à l'autre, on ne sait plus si deux résultats mesurent la même chose. Interlab répond à ça avec le principe "une implémentation par concept" : un seul module partagé pour les hooks, un seul module pour les statistiques, une même définition des artefacts.

Troisième problème : l'identité du corpus disparaissait. Par exemple, pour expliquer l'échec poutine, il faut savoir si le corpus d'entraînement contenait réellement assez d'exemples liés à poutine. Si le corpus n'est pas versionné comme artefact, on ne peut répondre qu'en prose. Interlab veut rendre cette question mesurable à partir d'un manifeste de corpus et d'un census.

L'architecture d'Interlab repose sur une ontologie d'artefacts. Les artefacts importants ici sont A1 à A11 dans la chaîne principale. A1 est le `corpus_manifest`, qui fixe le flux de données consommé. A3 est le `census_report`, qui peut mesurer la présence de concepts dans ce corpus. A5 est le `sae_checkpoint`, identifié par le hash de sa configuration et de ses poids. A6 est le `sae_certificate`, qui correspond au Gate G1 : la santé globale du SAE. Plus loin dans la chaîne, A7 serait la caractérisation des features, A8 le certificat d'une feature, A9 le résultat d'intervention, et A11 le rapport de revendication final. A10 est un peu différent : c'est une run card, écrite par les jobs, qui capture la provenance d'exécution.

Le principe technique le plus important est le content addressing. Un artefact n'est pas identifié par un chemin de fichier fragile du type `results/final/final2.json`. Il est identifié par un hash de son contenu. Ça veut dire que si le fichier change, son identité change aussi. Pour les checkpoints, la décision ED-27 définit l'identité comme le hash de `cfg.json` et `sae_weights.safetensors`, pas des logs ni de l'état d'optimiseur. C'est volontaire : la fonction du SAE dépend de la config et des poids, pas de fichiers incidentels.

Un autre point important est le manifeste de corpus, ED-28. L'idée n'est pas seulement de dire "j'ai utilisé FineWeb" ou "j'ai utilisé pile-10k". L'idée est de fixer le stream exact consommé par la formation, via une recette et un sous-ensemble. C'est ça qui rendrait possible une question du genre : combien de fois le SAE a-t-il vu un concept comme poutine ?

La philosophie d'Interlab se résume bien avec "certificates, not vibes". Une revendication ne devrait pas reposer sur une impression ou sur un nom de fichier, mais sur une chaîne de certificats. Et si la chaîne est incomplète, le système doit le dire explicitement : `UNCERTIFIED`, plutôt que de laisser croire que tout est validé.

Il y a aussi le principe "explore freely, claim expensively". L'idée n'est pas de ralentir toute exploration. On doit pouvoir lancer des tests rapides, chercher des candidates et faire des essais. Mais au moment de transformer un résultat en revendication scientifique, il faut payer le coût de la certification et de la provenance.

Mais la chaîne complète A1 vers A11 n'est pas encore exercée de bout en bout. A8, A9 et A11 sont conçus mais non peuplés. Le moteur d'intervention SS7 existe comme composant de trunk, avec des tests d'identité et de golden delta, mais aucun `intervention_result` A9 réel n'a encore été écrit dans le registre. L'interface SS8 entre Interlab et Lodestar existe comme design et stubs, mais les jugements Lodestar de ce rapport ont été faits en mode autonome, pas encore repliés dans Interlab.

Il faut dire ça explicitement parce que c'est une force méthodologique, pas une faiblesse rhétorique. Je peux défendre que la lane de certification est exercée. Je peux défendre que Lodestar a jugé les résultats. Je ne dois pas dire que le laboratoire complet A1 vers A11 a déjà produit un claim report certifié.

Un exemple que j'aime bien pour montrer la valeur d'Interlab est le problème de version. Le baseline avait initialement été noté comme `sae-lens` 3.23.0. La vérification ED-33 a montré que les checkpoints étaient en fait au format 6.x, donc entraînés sous 6.44.2. Le système a corrigé le baseline et reconstruit les artefacts de référence. C'est exactement le genre d'erreur silencieuse qu'une architecture fail-closed doit attraper : si la version logicielle sous les métriques est fausse, toutes les certifications deviennent suspectes.

Donc, quand je dis qu'Interlab est une contribution d'ingénierie, je ne veux pas dire "j'ai fait du tooling autour du projet". Je veux dire : j'ai construit une architecture qui transforme des fichiers expérimentaux en objets vérifiables, et qui force les revendications futures à être liées à une chaîne de provenance.

Transition :

Interlab répond à la question "d'où vient la preuve et quel est son statut ?". Lodestar répond à l'autre question : "comment est-ce qu'on mesure le comportement généré après steering ?"

---

## Diapositive 30 — Lodestar ferme la boucle d'évaluation

Temps visé : 4 minutes

Objectif oral : expliquer Lodestar comme plateforme d'évaluation, pas comme simple script de scoring.

Message clé : Lodestar transforme le steering en boucle expérimentale mesurée : générer, juger, analyser, raffiner.

Script :

Lodestar est la deuxième contribution d'infrastructure majeure. Son rôle est différent d'Interlab. Interlab s'occupe surtout de provenance, de certificats et d'identité des artefacts. Lodestar s'occupe de l'évaluation comportementale des générations produites par steering.

Le problème initial était très pratique : comment décider qu'une échelle de steering est bonne ? Sans Lodestar, il y a trois mauvaises options. Première option : faire un grep de mots-clés, par exemple compter les mentions de "cheese" ou "poutine". Mais ça ne mesure pas si la réponse est cohérente, ni si le concept est intégré naturellement, ni si le modèle répond encore à la consigne. Deuxième option : lire les générations à la main et choisir une échelle qui semble bonne. C'est utile pour explorer, mais c'est fragile scientifiquement. Troisième option : utiliser un LLM-as-judge sans protocole clair, sans cache, sans répétition, sans budget et sans métrique de fiabilité. Lodestar a été construit pour remplacer ces trois pratiques.

Le workflow est une boucle fermée. D'abord, un job de steering sur le cluster produit un fichier `generations.json`. Ce fichier contient les générations pour une feature, plusieurs échelles, parfois plusieurs conditions. Lodestar l'ingère et détecte les informations importantes : condition, scale, feature id, langue, à partir du fichier et des arguments.

Avant de juger, Lodestar peut faire une estimation de coût. C'est important parce qu'une campagne de steering peut produire beaucoup de textes, et chaque texte peut être jugé plusieurs fois sur plusieurs rubriques. Le mode `estimate` et le plafond `--budget` permettent d'éviter de lancer une évaluation dont le coût explose.

Ensuite, les générations sont envoyées au juge. Dans ce rapport, le juge réel est Claude Sonnet 4.5. Les rubriques centrales utilisées pour les résultats sont la cohérence, la pertinence conceptuelle, l'adhérence à la consigne et la naturalité d'intégration. La plateforme supporte aussi des rubriques complémentaires comme la mention littérale et les drapeaux de dégénérescence. Le point important est que Lodestar ne réduit pas la sortie à un seul mot-clé : il sépare plusieurs dimensions du comportement.

Chaque jugement est répété trois fois. À partir de ces répétitions, on peut mesurer la self-consistency du juge, notamment avec Krippendorff alpha. Dans les six runs standard du rapport, alpha est au moins 0,91 sur toutes les rubriques, et la cohérence est entre 0,983 et 0,998. Il faut être prudent ici : le juge fonctionne à température 0, donc alpha mesure un accord quasi déterministe entre répétitions à réglages fixes — un contrôle de déterminisme, et non la fiabilité, la stabilité ou une répétabilité validée du juge, ni un accord avec des humains. Aucune étude de corrélation humaine n'a été faite.

Le cache est aussi important. Les jugements sont stockés dans SQLite avec une clé basée sur le texte, la rubrique, le modèle juge et le nombre de répétitions. Donc si on régénère un rapport après avoir corrigé une analyse, on ne repaie pas les mêmes jugements. Le rapport mentionne explicitement le cas du bug `sweep_hash`, où le rapport a pu être régénéré à coût zéro à partir du cache.

Après les jugements, Lodestar calcule des métriques dérivées : la frontière cohérence-pertinence, la recherche de point opératoire, le control gap, et un score de steering efficacy. Pour cette présentation, la métrique la plus importante est la frontière. Le point opératoire n'est pas choisi parce qu'un exemple est joli. Il est choisi en maximisant la pertinence conceptuelle sous une contrainte de cohérence, par exemple cohérence au moins 5.

Le cas fromage illustre bien la boucle. Le sweep initial de 40 à 150 montre que l'échelle 40 est très cohérente mais a peu de steering, tandis que l'échelle 60 est plus pertinente conceptuellement mais tombe sous le plancher de cohérence. Cette information a motivé un sweep ciblé à 45, 50 et 55. C'est ce raffinement qui a trouvé l'optimum à 55.

Le cas Montréal montre l'autre valeur de Lodestar. Une estimation manuelle avait placé un bon point autour de 90, mais les données jugées ont plutôt déplacé la décision. Donc Lodestar ne sert pas seulement à confirmer une intuition : il peut la corriger.

En résumé, Lodestar transforme le steering en une boucle expérimentale : génération, jugement, rapport, décision, puis nouveau sweep si nécessaire.

Transition :

Cette boucle devient surtout utile parce qu'elle produit une interface inspectable, pas seulement un fichier JSON de scores.

---

## Diapositive 31 — Les rapports HTML deviennent l'interface d'analyse

Temps visé : 2 minutes 15 secondes

Objectif oral : montrer que les rapports Lodestar sont une contribution scientifique concrète.

Message clé : le rapport HTML est l'endroit où le résultat devient inspectable, auditables et réanalysable.

Script :

Cette slide montre un composite du rapport HTML Lodestar. Ce n'est pas juste une visualisation finale pour rendre les résultats plus jolis. Dans le projet, le rapport HTML a été l'interface principale d'analyse.

Chaque rapport est un fichier autonome qui s'ouvre dans un navigateur, sans serveur. Il contient la vue d'ensemble du run, la frontière cohérence-pertinence, les points opératoires optimaux, le control gap, la validation du juge, et le détail des générations. Donc si on voit un score moyen dans le tableau, on peut descendre jusqu'aux générations individuelles et voir quels jugements ont produit ce score.

Le point le plus fort, à mon avis, est l'épisode du bug `sweep_hash`. Un chercheur lisait le rapport HTML et a remarqué que la section des points opératoires ne semblait pas cohérente. Cette inspection visuelle a déclenché l'enquête qui a trouvé que les conditions d'ablation, avec scale 0, étaient mélangées aux sweeps de steering dans la frontière. Ce n'était pas un problème du juge : c'était un problème de groupement analytique.

Après correction, le rapport a été régénéré à partir du `run.json` et du cache de jugements, sans coût API supplémentaire. C'est exactement la valeur scientifique du système : on peut revoir et recalculer l'analyse sans refaire toute l'expérience.

Donc Lodestar n'est pas seulement "un LLM qui donne des notes". C'est une plateforme d'évaluation avec protocole, cache, coûts bornés, métriques dérivées et interface de revue.

Transition :

Avec cette infrastructure en place, on peut maintenant regarder le résultat principal : la feature 9056.

---

## Diapositive 32 — Résultat principal : feature 9056

Temps visé : 2 minutes

Objectif oral : présenter le résultat central sans l'exagérer.

Message clé : la feature 9056 suffit à induire un effet d'identité conceptuelle de type Golden Gate Claude, mais aucune ablation ne prouve encore sa nécessité.

Script :

Le résultat principal est la feature 9056, trouvée dans le SAE instruct `rwu04lpb`, couche 28, expansion 32 fois. C'est la candidate "cheese" qui reproduit le mieux l'effet recherché : quand on fixe son activation pendant la génération, le modèle commence à se décrire à travers le concept, tout en restant suffisamment cohérent et réactif au prompt.

Le point opératoire retenu est l'échelle 55. Il n'a pas été choisi parce que c'était le texte le plus amusant ou le plus extrême, mais parce que Lodestar l'a sélectionné sous une contrainte de cohérence. À cette échelle, la cohérence moyenne est 5,38 et la pertinence conceptuelle 5,50. L'adhérence à la consigne est 3,13, donc le modèle n'ignore pas complètement la question initiale, même si le concept de fromage influence fortement l'identité de la réponse. La naturalité d'intégration est plus basse, 1,75, ce qui montre que l'effet n'est pas parfait ni complètement naturel.

La phrase clé à dire prudemment est : 9056 est une démonstration de suffisance. Si on active cette feature, on produit l'effet. Mais on n'a pas encore fait le contrôle de nécessité : retirer ou ablater la feature pour montrer que l'effet disparaît. Donc je ne dois pas dire "cette feature est la cause unique". Je peux dire "cette feature suffit à produire l'effet dans cette configuration".

Cette nuance est importante parce qu'elle transforme le résultat en revendication scientifique défendable plutôt qu'en storytelling.

Transition :

La question suivante est : pourquoi l'échelle 55 est-elle le bon point, plutôt qu'une échelle plus haute qui donnerait plus de fromage ?

---

## Diapositive 33 — Pourquoi 55, et pas simplement « plus haut » ?

Temps visé : 1 minute 45 secondes

Objectif oral : expliquer le choix de l'échelle comme une décision méthodologique.

Message clé : le meilleur point n'est pas le maximum de pertinence, mais le meilleur compromis sous contrainte de cohérence.

Script :

Cette slide sert à justifier le choix de l'échelle. En steering, on pourrait être tenté de pousser l'échelle le plus haut possible parce que la pertinence conceptuelle augmente souvent avec l'intensité de l'intervention. Mais ce n'est pas le bon critère. À haute échelle, on peut obtenir plus de mentions du concept tout en détruisant la cohérence ou l'adhérence au prompt.

La règle utilisée ici est donc : maximiser la pertinence conceptuelle, mais seulement parmi les points qui gardent une cohérence d'au moins 5. Dans le sweep fromage, l'échelle 40 est très cohérente, avec 6,50, mais l'effet conceptuel est faible, 2,63. L'échelle 60 donne plus de pertinence, 7,75, mais la cohérence descend à 4,50, donc sous le plancher.

L'échelle 55 est le compromis : elle reste au-dessus du seuil de cohérence et augmente clairement la pertinence par rapport aux échelles plus faibles. C'est pour ça que je parle de point opératoire plutôt que de meilleur exemple.

Le point scientifique plus général est que Lodestar transforme une décision subjective en règle explicite. Même si on peut discuter du seuil exact, la décision est reproductible : quelqu'un d'autre peut appliquer la même règle au même sweep.

Transition :

Maintenant, il faut montrer que 9056 n'est pas seulement une feature qu'on a choisie parce qu'elle marche : elle ressort aussi d'une triangulation indépendante.

---

## Diapositive 34 — La candidate fiable est sélectionnée par convergence

Temps visé : 2 minutes

Objectif oral : présenter la triangulation comme contribution scientifique centrale.

Message clé : trois instruments indépendants classent les candidates dans le même ordre : 9056, puis 47735, puis 44189.

Script :

Cette diapositive est importante parce qu'elle montre que la méthode ne repose pas sur un seul signal. On a trois candidates portées assez loin dans le pipeline : 9056 pour fromage, 47735 pour UNESCO, et 44189 pour Eurovision.

La question est : est-ce que différents instruments donnent le même jugement sur leur qualité ? Le rapport montre que oui. La première famille de mesures vient du survey et de la caractérisation : est-ce que la feature semble sélective et conceptuellement propre dans les activations du corpus ? La deuxième vient du steering jugé par Lodestar : est-ce que l'intervention produit un texte cohérent, pertinent et encore lié au prompt ? La troisième vient des contrôles à taux apparié : est-ce que la candidate est vraiment meilleure qu'une feature qui s'active à une fréquence comparable ?

Ces trois mesures convergent vers le même classement : 9056 est la plus fiable, 47735 est intéressante mais moins bien intégrée, et 44189 doit être rejetée. C'est une contribution méthodologique importante, parce que la méthode sait dire non. Elle ne sert pas seulement à trouver une belle histoire positive.

Le cas 44189 est utile pour ça. Si la méthode acceptait toutes les candidates, elle ne serait pas falsifiable. Ici, Eurovision est rejetée par plusieurs signaux, donc la méthodologie a une capacité de discrimination réelle.

Transition :

La slide suivante détaille une partie de cette triangulation : les activations et les contrôles à taux apparié.

---

## Diapositive 35 — La sélectivité confirme le classement

Temps visé : 1 minute 45 secondes

Objectif oral : expliquer pourquoi les contrôles à taux apparié rendent la caractérisation plus crédible.

Message clé : 9056 se distingue dans les activations, tandis que 44189 échoue même contre son contrôle.

Script :

Ici, l'idée est de ne pas confondre rareté et qualité. Une feature peut sembler intéressante simplement parce qu'elle s'active rarement, ou parce qu'elle a quelques activations extrêmes. Le contrôle à taux apparié répond à cette objection : on compare la candidate à une autre feature qui s'active à une fréquence comparable, mais qui n'est pas censée porter le même concept.

Pour 9056, le signal est fort. Le maximum d'activation rapporté est 47,5, avec un taux de firing 14,5 fois la médiane de population, et 1003 événements de firing dans l'échantillon de 5000 documents. Le contrôle associé est plus faible. Donc la feature ne gagne pas seulement parce qu'elle est rare : elle a aussi une activation conceptuelle plus forte.

Pour 47735, le résultat est plus nuancé. UNESCO est une vraie candidate, mais son comportement en steering est moins bien intégré au prompt. Pour 44189, le rejet est beaucoup plus clair : son maximum est 8,5 et le contrôle à taux apparié la dépasse. Donc ce n'est pas une candidate que je voudrais défendre comme feature propre.

Le garde-fou important est que ces nombres viennent de `characterize_lite`. Le rapport précise que ce script est suffisant comme preuve au niveau du rapport, mais qu'il n'est pas encore un certificat Interlab A7 ou A8 produit par la lane complète.

Transition :

Les contrastes UNESCO et Eurovision montrent pourquoi la pertinence conceptuelle seule ne suffit pas.

---

## Diapositive 36 — Les contrastes rendent la méthode falsifiable

Temps visé : 1 minute 45 secondes

Objectif oral : expliquer que les candidates non principales valident la méthode de sélection.

Message clé : une feature utile ne doit pas seulement imposer un concept ; elle doit le faire sans détruire la réponse.

Script :

Cette slide sert à éviter un récit trop simple où 9056 marche et tout le reste serait juste moins intéressant. UNESCO et Eurovision donnent deux contrastes différents.

UNESCO est une candidate qui peut produire une pertinence conceptuelle élevée. Donc si on regardait seulement "est-ce que le concept apparaît ?", on pourrait être tenté de l'accepter. Mais Lodestar montre que l'adhérence au prompt et l'intégration naturelle sont plus faibles. Autrement dit, la feature peut prendre le dessus sur la réponse au lieu de s'intégrer dans une réponse encore contrôlée.

Eurovision est un rejet plus net. Elle est faible dans la caractérisation, faible contre son contrôle à taux apparié, et faible dans le steering jugé. C'est important parce que ça montre que la méthode ne sert pas seulement à confirmer une hypothèse positive. Elle permet aussi de dire : cette candidate ne mérite pas une revendication forte.

Le message que je veux faire passer est donc : la feature de steering fiable n'est pas celle qui maximise une seule dimension. Elle doit préserver un équilibre entre pertinence, cohérence, adhérence à la consigne et naturalité d'intégration.

Transition :

Je passe maintenant à un résultat qui demande une nuance différente : le multilingue.

---

## Diapositive 37 — Multilingue : attention à l'unité d'analyse

Temps visé : 1 minute 45 secondes

Objectif oral : présenter le résultat multilingue sans créer de contradiction avec le négatif poutine.

Message clé : le chevauchement top-20 mesure un voisinage de features, pas l'existence d'une feature unique et propre.

Script :

Cette slide est surtout là pour éviter une mauvaise interprétation. L'analyse multilingue ne cherche pas une seule feature monosemantique par concept. Elle regarde, pour chaque concept et chaque langue, les 20 features les plus activées en moyenne, puis elle mesure le chevauchement de ces ensembles entre langues.

Donc l'unité d'analyse est un ensemble top-20, pas une feature unique. C'est pour ça que le résultat poutine n'est pas contradictoire avec l'échec à trouver une feature poutine propre. Poutine peut avoir un chevauchement top-20 moyen relativement élevé, autour de 10 features partagées sur 20, sans qu'il existe une seule feature propre, stable et isolable qui porte "poutine" comme concept.

Le classement qualitatif est : world cup est le plus partagé, ensuite Québec, ensuite poutine, puis couscous plus bas. Ça suggère que certains concepts sont représentés de façon plus globale à travers les langues. Mais il faut garder la limite : seulement quatre concepts et quatre langues ont été testés, et il n'y a pas de census complet de prévalence qui permettrait de transformer ça en loi générale.

Donc la bonne formulation est : l'analyse donne un signal de globalité de voisinage conceptuel, pas une preuve de monosemanticité multilingue.

Transition :

Cette distinction rejoint les résultats négatifs, qui sont devenus des informations méthodologiques importantes.

---

## Diapositive 38 — Les résultats négatifs ont amélioré la méthode

Temps visé : 2 minutes 30 secondes

Objectif oral : montrer que les négatifs sont des résultats, car ils identifient des mécanismes et des limites.

Message clé : les échecs poutine, Montréal/Québec, base vers instruct et haute échelle bornent ce qu'on peut revendiquer.

Script :

Cette slide est importante parce qu'elle montre que le projet ne rapporte pas seulement le cas qui marche. Les résultats négatifs ont vraiment changé la méthode.

Premier négatif : poutine. Le projet a fait plus de 16 tentatives sur deux checkpoints sans isoler de feature poutine propre. Le mécanisme plausible, selon le rapport, est la couverture du corpus. Poutine est un concept plus régional et probablement moins présent dans le corpus utilisé, alors qu'un concept plus global comme Céline Dion est plus facilement trouvé. La conclusion n'est pas "on n'a pas eu de chance", mais plutôt : la couverture du corpus peut borner ce qui est découvrable, même si on augmente la largeur du dictionnaire SAE.

Deuxième négatif : Montréal/Québec. Ce cas est scientifiquement intéressant parce qu'il corrige un résultat initialement positif. Ce qui semblait être une feature Montréal ou Québec propre s'est révélé enchevêtré, notamment bilingue. Ça montre que la méthode doit tester plusieurs angles avant de revendiquer une feature conceptuelle.

Troisième négatif : le non-transfert base vers instruct. Une feature de chant, 19815, fonctionnait sur le modèle base mais devenait silencieuse sur le modèle instruct avec le même checkpoint. C'est seulement un cas, donc il ne faut pas généraliser trop fort, mais c'est assez pour dire qu'on ne peut pas supposer que la géométrie résiduelle du modèle base se transfère automatiquement au modèle instruct.

Quatrième négatif : la haute échelle. Sur la feature Montréal enchevêtrée, le modèle casse en fluence avant d'atteindre un régime stable "obsédé mais lisible" comme dans Golden Gate Claude. Ça ne veut pas dire que 9056 échoue de la même manière ; le rapport précise que ce comportement est spécifique à la feature enchevêtrée testée. Mais ça montre qu'augmenter l'échelle n'est pas une stratégie neutre.

Donc ces négatifs deviennent des garde-fous : corpus, enchevêtrement, géométrie instruct et échelle sont des dimensions qui contrôlent la validité des revendications.

Transition :

À partir de tout ça, on peut résumer ce qui est établi aujourd'hui et ce qui reste ouvert.

---

## Diapositive 39 — Ce qui est établi aujourd'hui

Temps visé : 2 minutes

Objectif oral : synthétiser l'état actuel sans donner l'impression que le projet est terminé.

Message clé : la maturité du projet vient du fait que les revendications sont séparées par niveau de preuve.

Script :

Cette slide est la carte de maturité actuelle du projet. Je veux distinguer trois catégories : ce qui est établi, ce qui est prudent, et ce qui n'est pas démontré.

Dans la colonne "établi", je peux défendre quatre choses. D'abord, 9056 suffit à induire un effet d'identité conceptuelle sous steering dans Qwen2.5-14B-Instruct. Ensuite, la triangulation donne le classement 9056 supérieur à 47735 supérieur à 44189. Troisièmement, Lodestar a été réellement exercé pour les points opératoires rapportés : les chiffres de cohérence et de pertinence ne sont pas des estimations manuelles. Quatrièmement, Interlab est vivant jusqu'au jalon G1, avec des artefacts de certification réels.

Dans la colonne "à interpréter prudemment", il y a les résultats qui sont utiles mais moins fermés. Le multilingue suggère une globalité qualitative, mais sur un petit ensemble de concepts et de langues. Le non-transfert base vers instruct est observé sur un cas. L'argument poutine-corpus est plausible et soutenu par les tentatives négatives, mais il manque un census complet. Et le juge Lodestar est cohérent en répétition, mais pas validé par comparaison humaine.

Dans la colonne "non démontré", on met les garde-fous majeurs. La nécessité de 9056 n'est pas démontrée. La généralité inter-modèle n'est pas démontrée parce que le bras Gemma Scope est staged mais pas run. La chaîne Interlab complète A1 vers A11 n'a pas encore produit de claim report. Et la validité humaine des scores Lodestar reste à faire.

Cette slide est utile parce qu'elle évite une conclusion trop forte. Le projet est plus mature, mais précisément parce qu'il sait dire ce qu'il ne peut pas encore revendiquer.

Transition :

La prochaine étape doit donc viser les garde-fous qui limitent le plus la force du résultat.

---

## Diapositive 40 — Prochaines décisions de recherche

Temps visé : 2 minutes

Objectif oral : terminer sur des décisions de recherche concrètes, pas sur une conclusion finale.

Message clé : l'ablation de 9056 est prioritaire parce qu'elle ferme le garde-fou causal principal.

Script :

Les prochaines décisions suivent directement de la carte de maturité.

La priorité numéro un est l'ablation de 9056. Aujourd'hui, la revendication est une suffisance : activer la feature produit l'effet. L'expérience d'ablation testerait la nécessité : si on retire ou neutralise 9056, est-ce que l'effet disparaît ? C'est la manière la plus directe d'augmenter la force causale du résultat principal.

La deuxième direction est Gemma Scope. Elle répond à une question différente : est-ce que ce qu'on a trouvé se généralise hors Qwen2.5-14B ? Le bras Gemma a été conçu et préparé, mais pas exécuté. Il permettrait de tester la robustesse du classement des features, du steering et des observations multilingues dans un autre modèle.

La troisième direction est le travail de circuits. Une fois que 9056 est stabilisée comme objet d'étude, on peut chercher quels mécanismes internes supportent son effet : attribution patching, ablations de têtes ou de MLP, ou analyse avec des outils de circuit tracing selon le modèle.

La quatrième direction est la grille layer par width. Elle est utile pour cartographier la santé des SAE à travers les couches et les expansions, mais je la mettrais après l'ablation et la généralisation, parce qu'elle augmente surtout la couverture descriptive.

Le critère de priorité que je proposerais est simple : choisir l'expérience qui ferme le garde-fou le plus important avec le coût expérimental le plus raisonnable. Selon ce critère, l'ablation de 9056 est la prochaine étape logique.

Phrase de clôture :

Donc l'état actuel n'est pas "le projet est terminé". L'état actuel est : on a un résultat positif quantitatif, une infrastructure d'évaluation exercée, une lane de certification vivante, et une liste claire de contrôles qui peuvent transformer ce résultat en revendication plus forte.

---

# Questions probables du PI et réponses préparées

## "C'est quoi Interlab en une phrase ?"

Interlab est une architecture de laboratoire pour expériences SAE : elle transforme les checkpoints, corpus, certificats, interventions et revendications en artefacts content-addressed, avec des gates explicites qui disent ce qui est certifié et ce qui ne l'est pas.

## "Quelle est la différence entre Interlab et Lodestar ?"

Interlab répond à la question de provenance et de statut : quel artefact a produit quel résultat, sous quelle version, avec quel certificat ? Lodestar répond à la question d'évaluation comportementale : une intervention de steering produit-elle un texte cohérent, pertinent, adhérent au prompt et naturellement intégré ? Dans cette campagne, Lodestar a été exercé de façon autonome ; l'intégration complète dans Interlab via A9/A11 est conçue mais pas encore peuplée.

## "Pourquoi Interlab n'est-il pas encore complet ?"

Parce que la partie exercée en production est la lane de certification jusqu'à A6/G1. Les schémas et certains composants existent pour la suite, notamment A8, A9 et A11, mais il n'y a pas encore d'artefacts vivants pour les résultats d'intervention ni de claim report complet. Le rapport le dit explicitement : c'est une frontière d'implémentation, pas une lacune d'architecture.

## "Est-ce que Lodestar est validé ?"

Lodestar n'est pas validé au sens de la fiabilité ou d'une répétabilité validée : le juge fonctionne à température 0, donc trois jugements par génération et Krippendorff alpha au moins 0,91 sur toutes les rubriques montrent un accord quasi déterministe entre répétitions à réglages fixes — un contrôle de déterminisme, pas une validation. Mais ce n'est pas une validation humaine. Il faut donc dire que le juge est cohérent avec lui-même dans le régime testé, pas qu'il est prouvé équivalent à un panel humain.

## "Pourquoi utiliser un LLM judge au lieu de lire les générations ?"

La lecture humaine est utile pour explorer, mais elle ne donne pas une règle reproductible pour choisir une échelle. Lodestar donne une frontière cohérence-pertinence, applique un seuil, garde les jugements en cache, borne les coûts et permet de réanalyser les runs. Donc il ne remplace pas le jugement scientifique ; il structure la décision.

## "Qu'est-ce que tu peux revendiquer exactement sur 9056 ?"

Je peux revendiquer que 9056 suffit à produire l'effet d'identité conceptuelle dans Qwen2.5-14B-Instruct, avec un point opératoire choisi par Lodestar à l'échelle 55. Je ne peux pas encore revendiquer que 9056 est nécessaire, ni que le mécanisme généralise à d'autres modèles.

## "Pourquoi poutine échoue alors que d'autres concepts marchent ?"

L'hypothèse soutenue par le rapport est la couverture du corpus. Poutine est un concept régional moins présent dans les données utilisées, donc il peut ne pas être isolé comme feature propre même avec plus de largeur SAE. Le point méthodologique est que la largeur du dictionnaire ne remplace pas la couverture conceptuelle du corpus.

## "Pourquoi le checkpoint principal est amber et pas green ?"

Parce que la bande de certification est un indicateur de santé globale du SAE, pas un classement direct des features. `rwu04lpb` est amber mais sain sur les métriques nécessaires, et la qualité de 9056 est établie par triangulation locale. Le seul checkpoint green n'est pas automatiquement celui qui contient la meilleure feature pour cette campagne.

## "Le résultat Montréal contredit-il le résultat 9056 ?"

Non. Montréal est une feature enchevêtrée et son comportement à haute échelle montre une casse de fluence avant un régime stable. 9056 reste cohérente dans la plage testée et a un point opératoire défendable. Le résultat Montréal sert de limite sur les features enchevêtrées, pas de réfutation du cas 9056.

## "Quelle serait la meilleure discussion à avoir après la présentation ?"

Je proposerais de décider si la prochaine étape doit maximiser la force causale du résultat principal ou tester sa généralité. Si on veut renforcer le résultat 9056, l'ablation est prioritaire. Si on veut tester l'external validity, Gemma Scope devient prioritaire.

---

# Version ultra-courte du message final

Si tu dois résumer la présentation en 30 secondes à la fin :

> Depuis la dernière rencontre, j'ai produit deux choses complémentaires. D'abord, une infrastructure : Interlab pour la provenance et la certification, Lodestar pour l'évaluation jugée et le choix de points opératoires. Ensuite, un résultat scientifique : la feature 9056 reproduit quantitativement un effet d'identité sous steering sur Qwen2.5-14B-Instruct. La revendication est volontairement bornée : c'est une suffisance, pas encore une nécessité, et la généralisation inter-modèle reste à tester. La prochaine étape la plus logique est donc l'ablation de 9056, suivie du bras Gemma Scope.
