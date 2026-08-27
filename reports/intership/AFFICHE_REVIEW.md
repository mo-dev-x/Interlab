# Révision de l'affiche — vérification et allègement

*2026-08-25 · porte sur `Summer internship affiche.pdf`*

---

## 1. Vérification des chiffres — tout est juste sauf un

J'ai repris chaque nombre de l'affiche contre le corpus.

**Correct, vérifié :**

| Affirmation | Statut |
|---|---|
| 2 796 cas de test · 102 modules de test | ✓ et les deux unités sont correctement distinguées |
| 583 → 2 796 cas collectés | ✓ |
| interlab 69 modules · 102 modules de test · 15 schémas | ✓ mesuré sur disque |
| sae-concept-lab 38 modules · 22 modules de test | ✓ |
| lodestar 28 modules · 14 modules de test · 118 documents | ✓ |
| couche 28, expansion 32× | ✓ (rwu04lpb, 163 840 features) |
| feature 9056, échelle 55 → 5,38 / 5,50 | ✓ |
| adhérence 3,13 | ✓ |
| échelle 60 : pertinence 7,75, franchit le plancher | ✓ (cohérence 4,50) |
| 2,6× · 50 % · 3,7× · signe inversé | ✓ |
| feature 2048 : 16/16, médiane +0,254, moyenne +0,290 | ✓ |
| 11/16, médiane +0,003, moyenne −0,023 | ✓ |
| Bonferroni sur 18 tests | ✓ |
| Templeton et al. 2024 · Cunningham et al. ICLR 2024 | ✓ références exactes |

**Une erreur à corriger :**

> **Figure 3 attribue « I'm an aged cheese… » à l'échelle 55.** La citation est authentique, mais
> elle provient de **l'échelle 80**, lors d'une confirmation interactive au REPL
> (`results/FEATURE_EXPERIMENT_LOG.md` §27a). À l'échelle 55, la réponse réelle à « Who are you? »
> est différente. Soit corriger l'étiquette en « échelle 80 », soit — mieux — utiliser la vraie
> sortie à l'échelle 55 (voir §2).

**Une faiblesse :** le volet « SANS PILOTAGE » est marqué *« reconstituée pour l'illustration »*.
C'est honnête, mais poser une citation reconstituée à côté d'une citation réelle affaiblit
précisément la figure censée être la démonstration concrète. De plus le volet non piloté est en
français et le volet piloté en anglais, ce qui fait ressembler la paire à une comparaison de
traduction plutôt qu'à une comparaison de pilotage. **Les vraies sorties existent** — inutile de
reconstituer quoi que ce soit.

---

## 2. Le résultat du pilotage : trois options, toutes réelles

### Option A — `gen16_lodestar_ui_result.png` ⭐ recommandée

Capture réelle de l'interface Lodestar affichant une génération pilotée, annotée en français.
Le public voit **le résultat et l'instrument en même temps** : l'identité de l'exécution, les trois
bras (sans pilotage / contrôle / pilotée), le texte verbatim, les six rubriques notées, et la
justification du juge.

*Réserve :* le texte de la capture est petit. À vérifier à la distance de lecture réelle de
l'affiche imprimée.

### Option B — `gen14_steering_result_text.png`

Trois volets côte à côte, texte verbatim, tous réels, même invite « Who are you? » à l'échelle 55 :
sans pilotage · **contrôle aléatoire** · feature 9056 amplifiée. Plus lisible de loin que la
capture. Le volet contrôle est ce qui transforme la figure en preuve : forcer une feature
quelconque à la même amplitude ne produit pas l'effet.

### Option C — les deux

A comme figure principale du bloc résultats, B en encadré plus petit. C'est le plus convaincant
mais cela consomme de la place.

---

## 3. Moins de texte : où couper

L'affiche est actuellement dominée par des puces dans les sections 1 à 4. Cibles concrètes :

| Section | Actuel | Proposition |
|---|---|---|
| **1. Le milieu de stage** | 5 puces institutionnelles | 2 lignes. Le logo IID dit déjà l'essentiel. |
| **3. Responsabilités** | 3 tâches × 3 puces = 9 puces | 1 ligne par tâche + la figure du pipeline en neuf étapes (`gen10`) qui *montre* les tâches au lieu de les décrire |
| **4. Compétences** | 3 colonnes × 3–4 puces | 2 puces par colonne, les plus spécifiques. Garder la phrase d'apprentissage — c'est la meilleure du panneau. |
| **6. Conclusion** | 2 colonnes × 3 puces | 2 puces par colonne |

**Ce qu'il ne faut pas couper :** l'hypothèse de travail en section 2 (encadrée). C'est ce qui rend
le résultat principal compréhensible pour la moitié non spécialiste de la salle.

**Gagné :** environ un tiers du texte, et la place pour agrandir le bloc résultats.

---

## 4. Codes QR — `gen15_qr_links.png`

Cinq codes, générés et scannables (`segno`, correction d'erreur H). **Les cinq URL sont
maintenant vérifiées.**

| Code | URL | Vérification |
|---|---|---|
| Dépôt scientifique | `github.com/mo-dev-x/Interlab` | remote git · **dépôt privé** |
| L'outil | `github.com/mo-dev-x/sae-concept-lab` | remote git · **dépôt privé** |
| Templeton et al. 2024 | `arxiv.org/abs/2605.29358` | ✓ titre et auteurs confirmés |
| Cunningham et al. | `arxiv.org/abs/2309.08600` | ✓ titre et auteurs confirmés |
| LinkedIn | `linkedin.com/in/mohamed-el-yazid-el-yaakoubi/` | ✓ fourni |

### ⚠ Les deux dépôts sont privés

`github.com/mo-dev-x/Interlab` et `github.com/mo-dev-x/sae-concept-lab` renvoient **404** à un
visiteur non authentifié. Le profil `mo-dev-x` existe et affiche six dépôts publics, aucun
n'étant ceux du stage.

**Conséquence : deux des cinq codes mènent à une page introuvable tant que les dépôts
restent privés.** Il faut soit les rendre publics avant la présentation, soit remplacer ces
deux codes par un seul pointant vers le profil `github.com/mo-dev-x`.

*Bonne nouvelle pour la mise en public :* l'historique Git des deux dépôts a été balayé
— aucun fichier de type jeton, `.env` ou identifiant n'a jamais été suivi dans l'un ou
l'autre. Rien ne bloque la publication de ce côté.

### Note sur le lien Templeton

Le code pointe vers **arXiv** plutôt que vers `transformer-circuits.pub`. Les deux sont
valides et il s'agit du même article ; la page originale dépasse 10 Mo, ce qui est pénible
à charger sur un téléphone en session d'affiches. La citation imprimée
(« Anthropic (2024) ») reste exacte : c'est la publication d'origine.

Taille minimale recommandée sur l'affiche : **3 cm de côté** pour un scan fiable à 50 cm.

---

## 5. Ordre des corrections

1. Corriger l'étiquette « échelle 55 » → « échelle 80 », **ou** remplacer la figure 3 par `gen16`.
2. Insérer le bandeau de codes QR en pied d'affiche.
3. Couper le texte des sections 1, 3, 4, 6 selon §3.
4. Agrandir le bloc résultats avec la place récupérée.
5. Scanner les cinq QR avant impression.
