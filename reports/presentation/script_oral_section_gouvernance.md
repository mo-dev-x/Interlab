# Script oral — section gouvernance & méthodologie (slides 41–48)

Durée visée : ~12 min. Auteur : Mohamed El Yazid — IID.

> **Règles de ce script.**
> 1. Les slides précédentes ont déjà été présentées : les résultats acquis sont
>    du contexte partagé, on ne les re-raconte pas.
> 2. Le fait qu'aucune nouvelle expérience n'ait encore tourné est dit **une
>    seule fois**, en ouverture. Ensuite on n'y revient plus.
> 3. Aucun code interne à l'oral (pas de A2, A8, G2, SS6, ED-19). Les codes
>    restent affichés à l'écran ; on les verbalise en langage clair.
> 4. Tout nombre énoncé porte son unité.

---

## Ouverture — avant la slide 41 (~50 s)

« Cette section ne contient pas de nouveau résultat de mesure, et je veux dire
tout de suite pourquoi, parce que c'est une raison de méthode.

Ce qu'on a vu jusqu'ici a été mesuré avec un juge externe en direct. Ce juge est
aujourd'hui inaccessible depuis l'environnement verrouillé : un conflit de
version entre deux bibliothèques bloque son adaptateur. Je peux lancer
l'expérience suivante demain, mais je la mesurerais alors avec un juge de
substitution — et j'obtiendrais un chiffre que je ne peux pas poser à côté des
précédents, parce qu'il ne sortirait pas du même instrument. Deux moitiés
mesurées sur deux instruments ne se comparent pas.

Donc ce que j'ai fait, c'est rendre l'expérience lançable et interprétable le
jour où le juge revient : le protocole est écrit, les hypothèses sont posées, et
les seuils de succès sont fixés avant d'avoir vu la moindre donnée. C'est le
sujet des huit prochaines slides.

Un mot pratique : vous allez voir des codes courts à l'écran — ce sont nos noms
internes d'artefacts. Je ne les lirai pas, je dirai à chaque fois ce qu'ils
contiennent. »

---

## Slide 41 — « Depuis la dernière rencontre » (45 s)

« Trois avancées depuis notre dernière rencontre.

La première : la chaîne de preuve a été corrigée. Nous avions une erreur sur
l'étape qui produit le certificat d'une feature.

La deuxième : l'expérience qui manque — celle qui teste si la feature fromage
est *indispensable* — est entièrement spécifiée et pré-enregistrée. Hypothèses,
groupes de contrôle, seuils, critère d'arrêt.

La troisième : l'environnement de calcul est en cours de verrouillage, pour
qu'un résultat produit dessus soit re-dérivable exactement.

Le reste de la section garde la règle des sections précédentes : je distingue en
permanence ce qui est établi, ce qui est conçu, et ce qui n'est pas démontré. »

---

## Slide 42 — La chaîne de preuve corrigée (1 min 45 s)

« Voici le chemin complet, du concept jusqu'à un score exploitable.

On part d'une liste de concepts, chacun accompagné de phrases-test. Ensuite on
compte à quelle fréquence le concept apparaît réellement dans le corpus.
Troisième étape, on construit l'index des activations : pour chaque feature, où
elle s'allume et à quelle intensité maximale.

Et c'est ici qu'était notre erreur. Nous avions placé la certification d'une
feature sur cette troisième étape. Elle n'y appartient pas : cette étape
construit un index, elle ne juge rien. Le certificat — celui qui atteste qu'une
feature est bien spécifique à un concept, et pas seulement corrélée — sort de
l'étape suivante, la validation. C'est là qu'est le point de contrôle.

Pourquoi ça change quelque chose, concrètement. Le job qui applique
l'intervention ne génère ses groupes de contrôle automatiques que si on lui
fournit ce certificat. Sans certificat, je n'obtiens que deux groupes : avec et
sans intervention. Je perds le groupe de contrôle qui teste si l'effet est
propre à cette feature. Autrement dit, avoir lancé l'expérience avant cette
correction m'aurait donné un résultat que je n'aurais pas su interpréter.

En bas, l'état réel du registre : les deux premières étapes existent, les
suivantes sont encore à zéro. La chaîne est juste ; elle n'est pas encore
peuplée. »

---

## Slide 43 — La moitié manquante (1 min 45 s)

> Slide conceptuelle. C'est ici qu'on définit les deux mots.

« Deux mots structurent toute cette section, et je veux les poser proprement.

Prenez un interrupteur et une lampe.

**La suffisance**, c'est : je pousse l'interrupteur vers le haut, et la lampe
s'allume. Appliqué à notre cas : je force la feature 9056 vers le haut, sur des
prompts parfaitement neutres, et du contenu fromage apparaît dans la génération.
Ça, c'est acquis — c'est ce qu'on a vu ensemble. La feature *peut* produire le
comportement.

**La nécessité**, c'est l'autre sens : je pousse l'interrupteur vers le bas, et
la lampe s'éteint. Appliqué à notre cas : je mets la feature 9056 à zéro sur des
prompts qui, naturellement, parlent de fromage — et le contenu fromage doit
chuter. C'est la partie qui manque.

Et voilà pourquoi les deux sont nécessaires. Si l'interrupteur allume la lampe
mais que la baisser ne l'éteint pas, alors quelque chose d'autre alimente aussi
la lampe. L'interrupteur n'est pas *le* contrôle, c'est *un* moyen parmi
d'autres. C'est exactement la faiblesse d'un résultat de suffisance tout seul :
il est compatible avec l'idée que le modèle a plusieurs routes vers le concept
fromage, et que j'en ai simplement trouvé une. La nécessité écarte cette
lecture. Les deux ensemble disent : cette feature est le mécanisme, pas
seulement un levier.

Sur le plan technique, ça ne demande aucun code nouveau. Le mécanisme qui force
une feature à une valeur existe déjà ; il suffit de lui demander la valeur zéro.
L'ablation s'exprime entièrement en configuration. »

---

## Slide 44 — Les groupes de contrôle (1 min 30 s)

« Isoler l'effet d'une feature demande plus qu'un simple avant/après. Quatre
groupes.

Le premier, sans aucune intervention, sur des prompts choisis pour amener
naturellement le sujet fromage. C'est le taux de référence.

Le deuxième : on met la feature 9056 à zéro, sur ces mêmes prompts. C'est
l'ablation elle-même.

Le troisième est le plus important de la slide. On met à zéro une *autre*
feature, choisie pour s'allumer à peu près à la même fréquence que 9056. Si
éteindre n'importe quelle feature de fréquence comparable faisait chuter le
contenu fromage, alors mon effet ne dirait rien sur 9056 — il dirait juste que
le modèle est fragile. Ce groupe répond à l'objection « vous avez simplement
cassé le modèle ».

Le quatrième : aucune intervention, mais sur des prompts d'un domaine voisin —
boulangerie, huile d'olive, tomates. Ça calibre le plancher du juge sur du
contenu alimentaire qui n'est pas du fromage.

Il y a un cinquième groupe produit automatiquement, mais il dégénère quand on
travaille à zéro : il devient identique au premier. Je le rapporte comme
vérification de cohérence, jamais comme preuve. »

---

## Slide 45 — Critères d'acceptation pré-enregistrés (2 min)

> Slide la plus forte de la section. Ne pas la presser.

« Tous les seuils que vous voyez ici ont été fixés avant qu'une seule donnée
n'existe.

Première hypothèse, la nécessité. Je calcule un intervalle de confiance à 95 %,
par rééchantillonnage au niveau du prompt. Pour valider, cet intervalle doit
être entièrement au-dessus de zéro — et il faut en plus une magnitude : soit une
taille d'effet d'au moins 0,5 écart-type, soit une réduction d'au moins 50 % du
score moyen.

Seconde hypothèse, la spécificité. Deux conditions, pas une. Il faut un effet —
l'ablation doit descendre significativement sous le groupe de contrôle apparié —
**et** une équivalence : ce groupe de contrôle doit rester à moins de 0,5 point
du groupe de référence, sur une échelle de jugement qui va de 1 à 10 points. Ce
second volet compte, parce qu'un test non significatif n'établit jamais une
équivalence ; il fallait donc fixer une marge explicite.

Ensuite, le verrou de réplication : trois tirages aléatoires indépendants. Les
deux hypothèses doivent tenir séparément sur les trois. Pas de moyenne entre
tirages, pas de sélection du meilleur, pas de relance si un seul échoue.

Sur l'agrégation : le juge note chaque génération trois fois. Ces trois notes
sont moyennées en un score unique par prompt avant toute analyse. Les traiter
comme trois observations indépendantes triplerait artificiellement l'effectif et
rétrécirait faussement tous les intervalles.

Et le point auquel je tiens le plus : j'ai pré-déclaré un troisième résultat
possible, « non concluant ». Avec dix prompts, le test d'équivalence à 0,5 point
peut manquer de puissance. Si l'intervalle est centré près de zéro mais trop
large, ce n'est ni un succès ni un échec — c'est un manque de puissance. Je
l'annonce maintenant pour ne pas pouvoir le réinterpréter après coup.

Rien ici n'a été choisi après avoir vu un résultat. C'est précisément ce qui
rendra le résultat crédible quand il arrivera. »

---

## Slide 46 — Infrastructure livrée (1 min 15 s)

« Ce qui est effectivement en production, vérifié au moment où je parle.

La liste de concepts est passée en version 1.1 : le concept fromage anglais est
ajouté, avec douze phrases-test que j'ai écrites moi-même. Son statut reste
partiel — il lui manque un type de contre-exemple, donc une des quatre mesures
du futur certificat restera non renseignée. J'y reviens dans les limites.

Le lanceur du comptage de corpus est publié et fusionné ; le comptage tourne
maintenant sur le cluster.

Et l'allocation GPU est standardisée sur les six lanceurs : nœud complet, quatre
GPU H100 par nœud. Ce n'est pas un détail d'intendance — les quatre SAE
certifiés l'ont été sous ce régime, et c'est ce qui rend les runs comparables
entre eux. »

---

## Slide 47 — Reproductibilité (1 min 30 s)

« Je présente le verrouillage d'environnement comme une contribution
scientifique, et je veux justifier ce mot.

Un certificat qui affirme « cette feature a telle spécificité » ne vaut rien si
on ne peut pas dire quelle version de quelle bibliothèque a produit ce nombre.
Ici la reproductibilité n'est pas un confort d'ingénierie : c'est la condition
pour que le certificat signifie quelque chose.

Donc : chaîne d'outils entièrement figée, aucune version flottante. Installation
strictement hors ligne, chaque paquet vérifié par empreinte cryptographique — le
nœud de calcul ne contacte jamais le réseau. Et chaque environnement construit
enregistre son propre manifeste : version de Python, plateforme, version de
CUDA, tous les paquets installés et leurs empreintes.

Le résultat concret : un autre laboratoire peut reconstruire cet environnement à
l'identique et re-dériver les mêmes nombres. »

---

## Slide 48 — Limites explicites (1 min 45 s)

« Je ferme par ce qui empêche de sur-interpréter cette section.

D'abord le juge. Un conflit de version entre deux bibliothèques maintient
l'adaptateur fermé, par conception — il refuse de tourner plutôt que de tourner
dégradé. C'est le chemin critique, et c'est une dépendance cassée, pas un choix
de priorité.

Ensuite, la distinction entre les deux étapes de l'expérience. La première étape
produit des générations, mais elle sert à valider la mécanique du pipeline ; ces
sorties ne compteront pas dans le rapport. Seule la seconde étape, notée par le
juge en direct, compte comme preuve.

Le futur certificat porte déjà deux limites connues. La caractérisation utilise
un juge de brouillon, pas l'annotation automatique de production. Et il manque
un type de contre-exemple dans la liste de concepts, donc la sensibilité y sera
honnêtement marquée non mesurée plutôt qu'estimée.

Enfin le corpus. La révision exacte du jeu de données amont n'a pas été
enregistrée au moment du téléchargement. Je ne peux pas la reconstruire sans
l'inventer, donc je ne l'invente pas. Le corpus est épinglé autrement, de façon
empirique : 601 369 documents, 400 millions de tokens, et une empreinte
cryptographique d'échantillon, avec la version du tokenizer épinglée exactement.
La limite est « je ne peux pas re-dériver depuis l'amont », pas « je ne sais pas
ce que j'ai consommé ».

Voilà où j'en suis : la moitié acquise tient, la moitié manquante est prête à
être mesurée, et une dépendance logicielle m'en sépare. »

---

## Annexe — questions probables

**« Pourquoi ne pas lancer avec le juge de substitution, quitte à refaire ? »**

Parce que les deux moitiés seraient mesurées sur deux instruments différents. Le
juge de substitution produit des scores déterministes de remplissage, pas des
jugements. Poser les deux chiffres côte à côte serait une erreur de méthode
visible. Cela dit, c'est exactement le rôle de la première étape : elle valide
toute la mécanique sans prétendre à une mesure.

**« N'as-tu pas passé trop de temps sur l'infrastructure ? »**

C'est une critique légitime. Ma réponse est que deux des blocages n'étaient pas
contournables. Sans le certificat de feature, le job d'intervention ne génère
pas le groupe de contrôle apparié — et une ablation sans ce groupe ne prouve
rien. Sans juge en direct, la mesure n'est pas comparable à l'existant. Le
troisième chantier, le verrouillage d'environnement, est un investissement dont
j'assume le coût.

**« Quelle est la prochaine mesure, et quand ? »**

Dès que le conflit de version est résolu : comptage, caractérisation,
validation, puis l'intervention sur un premier tirage comme test de pipeline,
puis les deux autres tirages, puis le jugement. Les critères d'acceptation étant
déjà fixés, l'analyse devient mécanique une fois les artefacts produits. Le
chemin critique est le conflit de dépendance, pas le protocole.

**« Et si la première hypothèse échoue ? »**

C'est prévu. Je ne relance pas avec des paramètres modifiés. Je diagnostique
trois choses : est-ce que les prompts amènent réellement du fromage sans
intervention ; est-ce que la feature de contrôle est assez proche en fréquence ;
et est-ce que l'hypothèse mécaniste est simplement fausse — 9056 pourrait
contribuer au contenu fromage par une voie différente de celle que je suppose.
Une ablation négative avec un bon groupe de contrôle reste un résultat
publiable.
