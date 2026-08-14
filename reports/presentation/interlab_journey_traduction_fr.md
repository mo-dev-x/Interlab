# Le parcours : de rien à une revendication certifiée

## Point de départ : vous avez une question

Votre question :

> Est-ce que la couche 28 de Qwen2.5-14B contient une feature « fromage » qui peut être steerée proprement ?

Ce que vous avez réellement :

- le modèle Qwen, déjà téléchargé;
- une idée vague : « fromage » est un concept;
- un numéro de couche : 28;
- une seed : on utilisera 42.

Ce que vous n'avez pas :

- aucune donnée indiquant si cette couche contient du fromage;
- aucune méthode encore établie pour le mesurer;
- aucune preuve que le steering fonctionne.

---

## Étape 1 : SS1 — Registre du corpus et des concepts

### Entrée de SS1

- un corpus, par exemple un sous-ensemble de FineWeb de 10 milliards de tokens;
- un concept que vous voulez sonder : « fromage ».

### Ce qui se passe

#### Étape 1a : créer un `CorpusManifest`

Vous calculez le hash du fichier de corpus complet. Vous enregistrez :

```text
Content hash: abc123...          # c'est l'identité
Source: FineWeb 2024-05
Token count: 10,000,000,000
Dedup rate: 2.3%                 # combien de passages dupliqués ont été retirés
Language split: 99.8% anglais, 0.2% autre
```

Ce sont de petites métadonnées, mais elles sont immuables. Tout résultat en aval qui dépend de ce corpus référencera ce hash. Si quelqu'un modifie le corpus en 2027, il recevra un nouveau hash, et les anciens résultats pointeront encore vers l'ancien corpus.

#### Étape 1b : créer une `ConceptBattery`

Vous écrivez des phrases de probe. Pour fromage :

```text
Probes (cible):
  "The cheese was sharp and aged."
  "I bought cheddar cheese at the market."
  "Cheese melts at high temperatures."
  ... (20 au total)

Contrôles (sans lien):
  "The building was made of steel."
  "He drove the car quickly."
  ... (20 au total)

Variantes sans le mot:
  "The product was sharp and aged."
  "I bought cheddar at the market."
  ... (20 au total, avec "cheese" retiré)
```

Ces phrases sont versionnées et hashées.

```text
ConceptBattery hash: def456...
```

Pourquoi utiliser des variantes sans le mot ? Parce que plus tard, quand vous testerez la spécificité, vous devrez savoir si la feature s'active parce qu'elle voit le mot « cheese », ou parce qu'elle comprend le concept de fromage. Les phrases sans le mot permettent de tester ça.

### Sortie de SS1

Trois artefacts :

```text
CorpusManifest (hash abc123...):
  métadonnées sur le corpus

ConceptBattery (hash def456...):
  phrases de probe versionnées

CensusReport (référence abc123... + def456...):
  tableau indiquant à quelle fréquence "cheese" apparaît
```

Exemple :

```text
CensusReport:
  concept: "cheese"
  corpus_hash: abc123...
  battery_hash: def456...
  frequency: 0.34 par million de tokens
  document_count: 234,567 documents contiennent "cheese"
  token_split: [0.02% dans des citations, 0.15% dans le contenu, ...]
```

Les trois artefacts sont des enregistrements immuables. Ils vivent dans le dépôt git ou dans le registre de manifestes, indexés par hash.

---

## Étape 2 : SS2 — Collecte de l'activation store

### Entrée de SS2

- modèle Qwen2.5-14B chargé;
- `CorpusManifest` avec le hash `abc123...`;
- numéro de couche : 28;
- batch size, configuration matérielle, etc.

### Ce qui se passe

Vous faites passer Qwen sur le corpus, token par token. À chaque position de token, vous extrayez le residual stream à la couche 28. C'est un vecteur de grande dimension, disons 4096 dimensions pour Qwen.

Nombres concrets :

```text
10 milliards de tokens × 4096 dimensions = 40,960,000,000,000 floats
À 4 octets par float, cela représente environ 164 To d'activations brutes.
```

Vous ne pouvez pas stocker ça naïvement. Donc vous :

- collectez les activations en morceaux, par exemple 1 million de tokens à la fois;
- écrivez chaque chunk sur disque en HDF5 ou en safetensors;
- calculez une QA de base : moyenne, écart-type, sparsité par dimension;
- hashez tout le store comme une seule unité.

### Sortie de SS2

Artefact `StoreManifest` :

```text
StoreManifest:
  store_hash: ghi789...           # hash de tous les fichiers d'activations
  corpus_hash: abc123...          # référence au corpus
  layer: 28
  model: "Qwen2.5-14B-Instruct"
  num_tokens: 10,000,000,000
  activation_dim: 4096

  QA_report:
    mean_activation_norm: 12.4
    sparsity (% zero): 0.001%
    outlier_check: PASS           # aucune dimension pathologique
    corruption_check: PASS        # aucun NaN/Inf
    coverage: PASS                # activations pour 99.99% des tokens
```

Les fichiers d'activations réels, par exemple 164 To, restent sur disque dans le cluster. Souvenez-vous du principe D1 : les artefacts lourds ne se déplacent pas. Seul le manifeste circule.

La transformation :

```text
tokens bruts → activations (un vecteur par token) → statistiques agrégées → manifeste
```

---

## Étape 3 : SS3 — Entraînement du SAE

### Entrée de SS3

- `StoreManifest` avec le hash `ghi789...`;
- configuration du SAE : `dict_size=32768`, `layer=28`, `seed=42`;
- hyperparamètres d'entraînement : learning rate, batch size, pénalité de sparsité, etc.

### Ce qui se passe

Vous entraînez un autoencodeur à compresser ces 10 milliards de vecteurs d'activations.

Avant l'entraînement :

- chaque activation est un vecteur de 4096 dimensions;
- le SAE apprend un encodeur : `4096 → 32768 features`;
- le SAE apprend un décodeur : `32768 → 4096`;
- la pénalité de sparsité force seulement quelques features à s'activer par token.

Pendant l'entraînement :

- pour chaque batch d'activations, le SAE apprend quelles directions du residual stream sont « utiles ».

Après 3 époques :

- vous avez 32768 directions de features apprises;
- certaines seront utiles, par exemple chocolat, fromage, nourriture;
- certaines seront du bruit;
- certaines seront des doublons.

Après l'entraînement :

- les poids sont gelés;
- vous enregistrez la seed 42;
- vous enregistrez le commit exact du code pour permettre la reproduction;
- vous calculez la perte de reconstruction : à quel point `decoder(encoder(activation))` récupère l'activation originale, avec une cible autour de 0,08.

### Sortie de SS3

Artefact `SAECheckpoint` :

```text
SAECheckpoint:
  checkpoint_hash: jkl012...

  model_config:
    dict_size: 32768
    layer: 28
    model: "Qwen2.5-14B-Instruct"

  training_config:
    seed: 42
    learning_rate: 0.0001
    sparsity_penalty: 0.001
    epochs: 3

  upstream_artifacts:
    store_hash: ghi789...          # quelles activations ont entraîné ce SAE ?

  code_commit: abc1234567...       # commit git du code d'entraînement

  weights:
    encoder: [matrice 32768 × 4096]
    decoder: [matrice 4096 × 32768]
    bias: [vecteur 32768]

  training_metrics:
    reconstruction_loss: 0.087
    final_sparsity: 0.02%          # 2% des features s'activent par token
```

La transformation :

```text
activations (un vecteur par token)
→ directions de features apprises (32768 directions, chacune en 4096 dimensions)
+ poids
```

À ce stade, vous avez :

- 32768 features potentielles;
- zéro connaissance certaine sur leur signification;
- zéro connaissance certaine sur lesquelles sont réelles ou seulement du bruit.

---

## Étape 4 : SS4 — Certification du SAE, Gate G1

### Entrée de SS4

- `SAECheckpoint` avec le hash `jkl012...`;
- activations de validation provenant d'un chunk de corpus séparé, non vu pendant l'entraînement.

### Ce qui se passe

Vous calculez trois mesures sur des activations fraîches.

#### Mesure 1 : perte de reconstruction

- encoder-décodeur sur des activations fraîches;
- comparaison entre la sortie et l'entrée;
- attente : moins de 0,1 est très bon; jusqu'à 0,2 peut être acceptable.

#### Mesure 2 : features mortes

- compter combien des 32768 features ne s'activent jamais dans le set de validation;
- les features mortes gaspillent la capacité du dictionnaire;
- attente : moins de 5% de features mortes; plus de 20% est mauvais.

#### Mesure 3 : polysémie ou doublons de décodeur

- vérifier si plusieurs features ont des vecteurs de décodeur presque identiques;
- si deux features sont redondantes, elles ne devraient pas toutes les deux exister;
- attente : aucun doublon; si plus de 10 apparaissent, quelque chose ne va pas.

### Sortie de SS4

Artefact `SAECertificate` :

```text
SAECertificate:
  checkpoint_hash: jkl012...

  schema_version: 2.0
  timestamp: 2026-07-26T14:32:00Z

  metrics:
    reconstruction_loss: 0.087        ✓ PASS (< 0.15)
    dead_feature_rate: 0.18%          ✓ PASS (< 5%)
    duplicate_decoder_pairs: 0        ✓ PASS (aucun)

  verdict: PASS

  gates_passed: [G1]

  upstream_artifacts:
    checkpoint_hash: jkl012...
```

Logique du Gate G1 :

```text
Si reconstruction_loss > 0.25: FAIL
  Le SAE n'apprend rien d'utile.

Si dead_feature_rate > 20%: FAIL
  La capacité est gaspillée.

Si duplicate_decoder_pairs > 5%: FAIL
  Problème de redondance ou de polysémie.
```

Si ce checkpoint échoue G1, rien en aval ne peut l'utiliser. Point final.

La transformation :

```text
32768 directions de features → 3 verdicts pass/fail → statut de certification PASS/FAIL
```

---

## Étape 5 : SS5 — Caractérisation des features

### Entrée de SS5

- `SAECheckpoint` avec le hash `jkl012...`, qui doit avoir passé G1;
- `CorpusManifest` avec le hash `abc123...`;
- un échantillon d'activations du corpus, par exemple 100 millions de tokens et non les 10 milliards complets.

### Ce qui se passe

Pour chacune des 32768 features, vous calculez :

- fréquence d'activation : à quelle fréquence cette feature s'active;
- tokens les plus activants : sur quels tokens cette feature s'active le plus fort;
- documents les plus activants : dans quels documents elle apparaît le plus;
- statistiques de tokens : quels types de tokens l'activent, par exemple noms, verbes, ponctuation.

Pour la feature 9056, par exemple :

```text
ActivationStats for feature_9056:
  fire_rate: 0.8%                  # 80,000 activations sur 10M tokens
  top_tokens: ["cheese", "cheddar", "mozzarella", "brie", "dairy"]
  top_documents: [doc_12345 (5 activations), doc_67890 (4 activations), ...]
  token_type_dist: [72% noms, 18% adjectifs, 10% autre]
  mean_activation_magnitude: 2.3
```

C'est purement descriptif. Vous ne testez encore rien causalement. Vous mesurez seulement ce que la feature fait sur un grand corpus.

### Sortie de SS5

Artefact `CharacterizationIndex` :

```text
CharacterizationIndex:
  checkpoint_hash: jkl012...
  corpus_hash: abc123...
  schema_version: 1.0

  features:
    9056:
      fire_rate: 0.008
      top_activating_tokens: ["cheese", "cheddar", ...]
      top_activating_docs: [...]
      mean_magnitude: 2.3
      entropy: 3.1
        # haut = activation dispersée, bas = activation concentrée

    47735:
      fire_rate: 0.003
      top_activating_tokens: ["UNESCO", "world heritage", ...]
      ...

    44189:
      fire_rate: 0.005
      top_activating_tokens: ["Eurovision", "song contest", ...]
      ...

    [... 32,765 autres features ...]
```

La transformation :

```text
activations (10M vecteurs)
→ statistiques par feature (32768 lignes de résumé)
→ index interrogeable
```

À ce stade, vous parcourez l'index et vous pensez :

> 9056 ressemble à fromage, 47735 ressemble à UNESCO, 44189 ressemble à Eurovision. Testons ces trois-là.

---

## Étape 6 : SS6 — Validation de feature, Gate G2

### Entrée de SS6

- `CharacterizationIndex` provenant de SS5;
- `ConceptBattery` avec le hash `def456...`;
- features à tester : 9056, 47735, 44189.

### Ce qui se passe

Pour la feature 9056, vous testez trois choses.

#### Test 1 : spécificité

Question :

> Est-ce que la feature s'active étroitement pour la cible ?

Vous envoyez les 20 probes cibles, par exemple "The cheese was sharp...", dans Qwen. Vous mesurez si la feature 9056 s'active.

```python
cheese_probes = ["The cheese was sharp...", "I bought cheddar...", ...]

for prompt in cheese_probes:
    activation = model(prompt, layer=28, project=sae)
    fire_9056 = activation["feature_9056"] > 0.1

specificity = mean(fire_9056 across cheese_probes)
# Résultat: 0.92
# La feature s'active dans 18 prompts fromage sur 20.
```

#### Test 2 : sensibilité

Question :

> Est-ce qu'elle s'active seulement pour la cible ?

Vous envoyez les 20 probes de contrôle, sans lien avec le concept. Vous mesurez si la feature 9056 ne s'active pas.

```python
control_probes = ["The building was steel...", "He drove quickly...", ...]

for prompt in control_probes:
    activation = model(prompt, layer=28, project=sae)
    fire_9056 = activation["feature_9056"] > 0.1

sensitivity = 1 - mean(fire_9056 across control_probes)
# Résultat: 0.87
# Elle ne s'active pas dans 17 contrôles sur 20; 3 faux positifs.
```

#### Test 3 : sélectivité

Question :

> Est-ce qu'elle comprend le concept, pas seulement le mot ?

Vous envoyez les 20 probes sans le mot, par exemple "The product was sharp and aged...". Vous mesurez si la feature 9056 s'active encore.

```python
word_absent_probes = ["The product was sharp...", "I bought cheddar at market...", ...]

for prompt in word_absent_probes:
    activation = model(prompt, layer=28, project=sae)
    fire_9056 = activation["feature_9056"] > 0.1

selectivity = mean(fire_9056 across word_absent_probes)
# Résultat: 0.81
# Elle s'active dans 16 prompts sans le mot sur 20.
# Haute sélectivité = "je comprends fromage même sans le mot cheese".
```

### Sortie de SS6

Artefact `FeatureCertificate` pour la feature 9056 :

```text
FeatureCertificate:
  checkpoint_hash: jkl012...
  feature_index: 9056
  concept: "cheese"
  schema_version: 2.0

  metrics:
    specificity: 0.92          ✓ PASS (>= 0.75)
    sensitivity: 0.87          ✓ PASS (>= 0.75)
    selectivity: 0.81          ✓ PASS (>= 0.70)

  verdict: PASS
  gates_passed: [G1, G2]

  judge_version: "claude-opus-4-8"
  rubric_version: "v2.0"
  prompt_template_version: "v1.1"

  upstream_artifacts:
    checkpoint_hash: jkl012...
    battery_hash: def456...
```

Logique du Gate G2 :

```text
Si specificity < 0.75: FAIL
  La feature ne s'active pas assez pour la cible.

Si sensitivity < 0.75: FAIL
  La feature s'active trop souvent pour des choses sans lien.

Si selectivity < 0.70: FAIL
  La feature dépend du mot, pas du concept.
```

Si la feature 9056 échoue G2, vous ne la steererez pas. Vous retournez à l'index de caractérisation et vous essayez une autre feature, par exemple 47735.

La transformation :

```text
index de features + phrases de probe
→ trois scores entre 0 et 1
→ verdict pass/fail
```

---

## Étape 7 : SS7 — Moteur d'intervention, Gate G3

### Entrée de SS7

- `FeatureCertificate` pour la feature 9056, ayant passé G2;
- `SAECheckpoint` avec le hash `jkl012...`;
- modèle Qwen;
- configuration de steering : `feature=9056`, `scales=[10, 20, 30, 50, 80]`.

### Ce qui se passe

Vous allez faire agir Qwen comme si la feature 9056 était activée.

Mécanisme :

1. **Forward pass normal**  
   Vous faites passer un prompt dans Qwen normalement, puis vous enregistrez le residual stream à la couche 28.

2. **Extraction de la direction de feature**  
   Le décodeur du SAE contient un vecteur de poids pour la feature 9056, une direction en 4096 dimensions. On peut l'appeler `w_9056`.

3. **Ajout d'un multiple de cette direction**  
   Vous modifiez le residual stream en ajoutant `scale × w_9056`.

4. **Continuation du forward pass**  
   Vous laissez Qwen continuer à partir du residual stream modifié.

Pseudocode :

```python
prompt = "I went to the store and bought"
scale = 55

# Forward pass normal
activations = qwen.forward_pass(prompt, layer=28)
residual_stream = activations[:, -1, :]  # dernier token, couche 28

# Steering
feature_direction = sae.decoder[:, 9056]  # direction 4096-D pour fromage
steered_residual = residual_stream + scale * feature_direction

# Continuer depuis le résiduel modifié
output = qwen.continue_forward(steered_residual, from_layer=28)

# Résultat possible:
# "I went to the store and bought cheddar cheese. It was sharp and aged well."
```

### Test d'identité G3 — crucial

La librairie de hooks vérifie :

- **Delta-form** : est-ce qu'on a seulement ajouté au residual stream, sans le corrompre ?
- **Orthogonalité** : est-ce que `scale × w_9056` est orthogonal, ou presque orthogonal, aux directions résiduelles propres de Qwen ?
- **Réversibilité** : si on steer avec `scale=0`, est-ce qu'on récupère la baseline ?

Si l'un de ces tests échoue, vous avez introduit un bug. G3 l'attrape.

### Sortie de SS7

Artefact `InterventionResult` :

```text
InterventionResult:
  checkpoint_hash: jkl012...
  feature_index: 9056

  interventions:
    scale_10:
      baseline_generation: "I went to the store and bought milk."
      steered_generation: "I went to the store and bought milk and cheese."
      hook_audit: PASS (delta-form, orthogonal)

    scale_20:
      baseline_generation: "I went to the store and bought milk."
      steered_generation: "I went to the store and bought sharp cheddar cheese."
      hook_audit: PASS

    scale_55:
      baseline_generation: "I went to the store and bought milk."
      steered_generation: "I went to the store and bought aged brie and sharp cheddar."
      hook_audit: PASS

    [... scale_80 ...]

  control_arm:
    scale_55_random_feature:
      baseline_generation: "I went to the store and bought milk."
      steered_generation: "I went to the store and bought milk."
      hook_audit: PASS

  gates_passed: [G1, G2, G3]
```

La transformation :

```text
residual stream + direction de feature
→ residual stream modifié
→ générations différentes
```

---

## Étape 8 : SS8 — Évaluation comportementale, Gate G4

### Entrée de SS8

- `InterventionResult` avec les scales 10, 20, 30, 50, 55, 80 et le contrôle;
- juge Lodestar, par exemple Claude Opus;
- rubrique d'évaluation.

### Ce qui se passe

Vous envoyez chaque génération à Lodestar, qui utilise un LLM juge pour attribuer des scores.

Pour chaque paire de générations, baseline et steered :

```text
Prompt:
  "Évalue ces deux réponses. Est-ce que le steering vers 'cheese'
   améliore la cohérence et la pertinence ?"

Baseline:
  "I went to the store and bought milk."

Steered:
  "I went to the store and bought aged brie and sharp cheddar."

Scores du juge:
  coherence_change: +0.18
    La sortie steered est légèrement plus cohérente.

  relevance_change: +0.22
    La sortie steered est plus pertinente pour la cible "cheese".

  control_quality: 5/5
    Pas d'hallucination, pas de syntaxe cassée.
```

Le juge fait cela de manière cohérente sur toutes les échelles et tous les bras de contrôle. Les résultats sont mis en cache par Lodestar, donc les évaluations répétées sont gratuites.

### Sortie de SS8

Enregistrements de jugement, intégrés dans `InterventionResult` :

```text
Lodestar_Judgments:
  judge_model: "claude-opus-4-8"
  rubric_version: "v2.0"

  scale_10:
    coherence_delta: +0.08
    relevance_delta: +0.12

  scale_20:
    coherence_delta: +0.14
    relevance_delta: +0.18

  scale_55:
    coherence_delta: +0.18
    relevance_delta: +0.22

  scale_80:
    coherence_delta: +0.16
    relevance_delta: +0.20

  control_scale_55:
    coherence_delta: +0.01
    relevance_delta: -0.02
```

### Logique G4 : test statistique

Questions :

- Existe-t-il une échelle où le steering améliore significativement la cohérence ou la pertinence ?
- L'effet steered est-il plus grand que l'effet du contrôle, par exemple le steering d'une feature non liée ?
- La taille d'effet est-elle significative, et non seulement `+0.01` dans un score bruité ?

Dans votre cas fictif :

```text
scale=55:
  coherence +0.18
  relevance +0.22

control:
  -0.02

Conclusion:
  effet réel et directionnel → PASS G4
```

La transformation :

```text
générations textuelles
→ scores du juge
→ comparaison statistique
→ pass/fail sur la taille d'effet
```

---

## Étape 9 : SS9 — Assemblage des revendications

### Entrée de SS9

Tous les artefacts amont :

- `SAECertificate`, G1 : ✓;
- `FeatureCertificate`, G2 : ✓;
- `InterventionResult` avec audit du hook, G3 : ✓;
- jugements Lodestar, G4 : ✓.

### Ce qui se passe

SS9 pose les questions suivantes :

- est-ce que tous les gates existent et passent ?
- est-ce qu'ils utilisent les versions de schéma actuelles ?
- est-ce que les versions du juge sont compatibles ?

Exemple de chaîne de certificats :

```text
Certificate Chain for "cheese feature":
  ├─ SAECheckpoint (jkl012...)
  │  └─ SAECertificate (G1)
  │     verdict: PASS ✓
  │
  ├─ FeatureCertificate for feature_9056 (G2)
  │  metrics: spec=0.92, sens=0.87, selec=0.81
  │  verdict: PASS ✓
  │
  ├─ InterventionResult
  │  └─ Identity test (G3)
  │     verdict: PASS ✓
  │
  └─ Lodestar judgments (G4)
     scale=55: coherence +0.18, relevance +0.22
     control: coherence -0.02
     verdict: PASS ✓

All gates: PASS
Schema versions: all current
Evaluation versions: all compatible
Judge models: all claude-opus-4-8 (consistent)

Final verdict: CERTIFIED
```

### Sortie de SS9

Artefact `ClaimReport` :

```text
ClaimReport:
  claim_id: "qwen-layer28-cheese-2026-07-26"
  timestamp: 2026-07-26T18:45:00Z

  hypothesis: "Qwen2.5-14B layer 28 contains a cheese-detector feature"

  certificate_chain:
    sae_checkpoint: jkl012...
    sae_certificate_g1: PASS
    feature_index: 9056
    feature_certificate_g2: PASS (spec=0.92, sens=0.87, selec=0.81)
    intervention_certificate_g3: PASS (delta-form, orthogonal)
    behavioral_certificate_g4: PASS (coherence +0.18, relevance +0.22, p<0.05)

  statistical_summary:
    effect_size_coherence: 0.18
    effect_size_relevance: 0.22
    control_effect_coherence: -0.02
    net_effect_significant: true

  certification_status: CERTIFIED
  gates_passed: [G1, G2, G3, G4]

  conclusion:
    "Feature 9056 in Qwen2.5-14B layer 28 is a monosemantic cheese detector.
     Steering it at scale=55 produces coherent, relevant generations mentioning
     cheese-related concepts, with effect sizes statistically significant vs. controls."
```

La transformation :

```text
résultats bruts, certificats, scores et jugements
→ chaîne unifiée
→ verdict unique pass/fail
```

---

## Tout mettre ensemble : diagramme de flux de données

```text
Étape 1 (SS1):
  Corpus + Concepts
      ↓
  [CorpusManifest, ConceptBattery, CensusReport]

Étape 2 (SS2):
  [CorpusManifest] + Modèle + Couche
      ↓
  [StoreManifest] ← le store d'activations de 164 To reste sur le cluster

Étape 3 (SS3):
  [StoreManifest] + config SAE + seed
      ↓
  [SAECheckpoint] ← 32768 directions de features apprises

Étape 4 (SS4) — G1:
  [SAECheckpoint] + activations de validation
      ↓
  [SAECertificate: reconstruction, features mortes, polysémie]
      ↓
  PASS/FAIL ← si FAIL, on s'arrête ici

Étape 5 (SS5):
  [SAECheckpoint] + [CorpusManifest] + échantillon d'activations
      ↓
  [CharacterizationIndex] ← 32768 lignes de stats par feature
      ↓
  Parcourir et sélectionner des candidates, par exemple feature 9056

Étape 6 (SS6) — G2:
  Feature 9056 + [ConceptBattery]
      ↓
  [FeatureCertificate: spécificité, sensibilité, sélectivité]
      ↓
  PASS/FAIL ← si FAIL, essayer une autre feature

Étape 7 (SS7) — G3:
  [SAECheckpoint] + feature 9056 + scales [10, 20, ..., 80]
      ↓
  [InterventionResult: générations + audit du hook]
      ↓
  PASS/FAIL ← si FAIL, corriger le hook

Étape 8 (SS8) — G4:
  [InterventionResult] + juge Lodestar
      ↓
  [Lodestar judgments: scores de cohérence/pertinence]
      ↓
  Test statistique: PASS/FAIL ← si FAIL, essayer une autre échelle

Étape 9 (SS9):
  [SAECertificate G1] + [FeatureCertificate G2]
  + [InterventionResult G3] + [Lodestar G4]
      ↓
  [ClaimReport]
      ↓
  CERTIFIED ← chaîne complète, tous les gates ont passé
  OU
  DRAFT ← gate manquant ou certificat périmé
```

---

## Idée clé : chaque étape répond à une question

| Étape | Question | Type de réponse |
|---|---|---|
| SS1 | Quelle distribution le modèle a-t-il vue ? | Census et fréquence |
| SS2 | Quelles sont les activations à cette couche ? | Manifeste d'activation store |
| SS3 | Peut-on décomposer cette couche en features ? | Poids du SAE |
| SS4 | Ce SAE est-il sain ? | PASS/FAIL, G1 |
| SS5 | Quelles features semblent interprétables ? | Liste classée avec statistiques |
| SS6 | Cette feature est-elle un vrai concept ? | PASS/FAIL, G2, avec scores |
| SS7 | Peut-on steer cette feature proprement ? | PASS/FAIL, G3, plus générations |
| SS8 | Le steering produit-il le comportement voulu ? | PASS/FAIL, G4, plus tailles d'effet |
| SS9 | Est-ce une revendication défendable ? | CERTIFIED/DRAFT |

Chaque étape transforme les données, et chaque gate décide s'il faut continuer ou revenir en arrière.

