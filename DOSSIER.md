# DOSSIER — Analyse Itérative des Verbatims R6

*Analyse du 2026-03-04 — basée sur le code existant*

---

## 1. Diagnostic de l'existant

### Ce que fait le code actuel

`analyze_verbatim()` dans `ai_analyze.py` envoie un unique appel Ollama avec le prompt `analyze_verbatim.txt`. Ce prompt demande au LLM d'accomplir simultanément cinq tâches distinctes sur le verbatim brut :

1. Segmenter le texte en passages significatifs
2. Associer chaque passage à une capacité R6 (parmi 18)
3. Valider implicitement que le registre linguistique (Halliday) correspond au niveau S/O/I
4. Évaluer le niveau de maturité sur l'échelle correspondante
5. Rédiger l'interprétation analytique en 2-4 phrases

Le résultat est une liste d'`AnalyzedExtract` (text, tag, capacity_id, maturity_level, confidence, interpretation) persistée en base comme `Extract` + `Interpretation`.

### Problèmes structurels identifiés

**Charge cognitive excessive pour le LLM.** Condenser cinq décisions en un seul appel contraint le modèle à des compromis implicites. Une hésitation sur la segmentation peut contaminer l'identification de la capacité, qui contamine l'évaluation de maturité. Le modèle ne peut pas "revenir en arrière" entre ses propres décisions.

**Validation Halliday absente.** Le prompt mentionne les niveaux S/O/I mais ne force pas un raisonnement Halliday explicite. La contrainte linguistique (registre institutionnel vs analytique vs opérationnel) n'est pas vérifiée indépendamment : elle est simplement espérée. En pratique, un extrait sur les pratiques d'un collectif (niveau O) peut se retrouver taggué I ou S sans que rien ne le signale.

**Opacité du raisonnement.** Quand le consultant rejette une interprétation, il ne peut pas savoir si l'erreur vient du découpage, de l'identification de la capacité, ou de l'évaluation de maturité. Tout corriger revient à tout refaire manuellement.

**Confiance non calibrée.** Le score `confidence` est produit en une passe, sans recoupement. Il reflète l'incertitude globale du modèle sur un résultat composite, pas une mesure fiable de la solidité de chaque décision intermédiaire.

**Sélectivité non contrôlée.** Le prompt demande "3 à 8 extraits les plus significatifs". La sélection est entièrement subjective au modèle. Rien ne garantit la couverture des trois niveaux, des trois axes, ou des deux pôles quand ils sont présents dans le verbatim.

---

## 2. Principe de l'approche itérative

L'idée de base est de décomposer le traitement en étapes séquentielles où la sortie de chaque étape alimente l'entrée de la suivante, et où chaque étape correspond à une question précise et isolée.

### Les trois questions à traiter séparément

**Question 1 — Où sont les passages pertinents ?**
Segmenter le verbatim en blocs sémantiques cohérents, indépendamment de toute décision sur les capacités. Cette étape est linguistique et structurelle, pas analytique R6.

**Question 2 — Quel est le registre de ce passage ?**
Pour chaque bloc, identifier la capacité R6 la plus pertinente en appliquant explicitement le filtre Halliday : quel est le sujet grammatical dominant, quel type de processus décrit-il (matériel, relationnel, mental) ? Cette question doit être répondue avant d'aller à la maturité.

**Question 3 — Quel est le niveau de maîtrise observable ?**
Pour chaque bloc dont la capacité est identifiée, évaluer la maturité en confrontant le passage à l'échelle correspondante (I6/O6/S6) et rédiger l'interprétation diagnostique.

### Flux de données

```
Verbatim brut
    │
    ▼  [Étape 1 : Segmentation]
Blocs sémantiques (texte + contexte thématique)
    │
    ▼  [Étape 2 : Identification capacité + validation Halliday]
Blocs annotés (capacity_id + level_code validé + justification Halliday)
    │
    ▼  [Étape 3 : Évaluation maturité + interprétation]
Interprétations complètes (maturity_level + confidence + texte analytique)
```

---

## 3. Architecture proposée

### Principe de batchage par étape

La contrainte principale est Ollama local : multiplier les appels LLM par le nombre de blocs serait prohibitif en latence pour des verbatims longs. La solution est de traiter **toutes les étapes en batch** : une étape = un appel Ollama, le prompt traitant l'ensemble des blocs en une seule fois.

Cela maintient le nombre d'appels LLM à 3 par verbatim (contre 1 aujourd'hui), tout en séparant les responsabilités cognitives.

### Étape 1 — Segmentation

**Un appel Ollama.** Input : verbatim brut + métadonnées entretien (sujet, rôle, level_code).

Le LLM produit une liste de blocs numérotés, chacun contenant :
- Le texte exact du bloc (citation littérale du verbatim)
- Un thème résumé en une phrase (label contextuel)
- Le type de contenu : observable comportemental, description organisationnelle, posture stratégique, méta-discours à exclure

Les blocs de type "méta-discours" (questions du consultant, digressions hors sujet) sont marqués comme `irrelevant: true` et exclus des étapes suivantes.

Le LLM n'est PAS demandé de faire de la R6 ici. Il fait de la linguistique de surface et de la cohérence sémantique. La tâche est ainsi plus simple et plus fiable.

### Étape 2 — Identification de la capacité + validation Halliday

**Un appel Ollama.** Input : liste de blocs (ceux non marqués irrelevant) + liste complète des 18 capacités avec leur définition courte + règles Halliday par niveau (depuis `halliday_rules.json`).

Pour chaque bloc, le LLM produit :
- Le `capacity_id` proposé (ex: "O2b")
- Le `level_code` confirmé ("S", "O" ou "I") après application des critères Halliday
- Un indicateur `halliday_consistent` (booléen) : le registre du bloc correspond-il bien au niveau de la capacité identifiée ?
- Une justification courte (1-2 phrases) citant les marqueurs linguistiques du bloc

Si `halliday_consistent: false`, le LLM doit proposer une capacité alternative dont le level_code correspond au registre observé, ou indiquer que le bloc est ambigu (`capacity_id: null`).

Le fait de demander explicitement la justification Halliday force un raisonnement observable — pas une intuition globale.

### Étape 3 — Évaluation de la maturité + interprétation

**Un appel Ollama.** Input : liste de blocs avec leur `capacity_id` validé + échelle de maturité correspondante au level_code (I6/O6/S6).

Pour chaque bloc, le LLM produit :
- Le `maturity_level` selon les descripteurs de l'échelle (insuffisant, émergent, satisfaisant, avancé, expert)
- Un score `confidence` (0.0 à 1.0) portant uniquement sur l'évaluation de maturité, pas sur l'ensemble
- Le texte de l'interprétation (2-4 phrases) ancré dans les observables du bloc et les critères de l'échelle

La tâche est ici purement évaluative. Le LLM n'a plus à se demander quelle capacité ni quel registre — ces décisions sont déjà prises. Il peut se concentrer sur la qualité de l'interprétation.

---

## 4. Compatibilité avec le schéma de données existant

Le schéma `Extract → Interpretation` est structurellement compatible avec l'approche itérative. La correspondance est directe :

| Étape itérative | Table existante | Colonnes utilisées |
|---|---|---|
| Étape 1 : bloc sémantique | `Extract` | `text`, `display_order` |
| Étape 2 : capacité identifiée | `Extract` | `tag` (capacity_id) |
| Étape 3 : interprétation | `Interpretation` | `capacity_id`, `maturity_level`, `confidence`, `text`, `status` |

**Ce qui manque dans le schéma actuel :**

Deux informations issues de l'Étape 2 n'ont pas de colonne dédiée :
- La justification Halliday (texte court)
- L'indicateur `halliday_consistent`

**Option A (sans modification du schéma) :** Intégrer la justification Halliday dans le texte de l'`Interpretation` comme préambule. Cela préserve le schéma mais mélange deux types d'information dans le même champ.

**Option B (modification minimale) :** Ajouter deux colonnes à `Extract` : `halliday_note` (Text, nullable) et `halliday_ok` (Boolean, nullable). Migration idempotente triviale à ajouter à `init_db()`. Cela permet d'afficher la validation Halliday dans l'UI de revue sans polluer le texte de l'interprétation.

La recommandation est l'**Option B** : le gain en lisibilité et traçabilité justifie largement la migration d'une colonne. La migration est du même type que `_migrate_drop_observable_column()` — PRAGMA + rebuild.

---

## 5. Impact sur l'UI

### Ce qui ne change pas

Le flux principal de l'utilisateur reste identique :
1. Saisir le verbatim dans `mission_tab_verbatim.py`
2. Cliquer sur "Analyser"
3. Réviser les interprétations dans `mission_tab_interpretations.py` (validate/reject/correct)

L'approche itérative est un changement de moteur, pas d'interface.

### Ce qui s'améliore naturellement

**Retour de progression par étape.** Actuellement, l'`_AnalyzeWorker` émet un signal unique à la fin. Avec 3 étapes séquentielles, il peut émettre des signaux de progression intermédiaires : "Segmentation terminée (8 blocs)... Identification des capacités... Interprétation en cours...". L'UI affiche déjà une barre de progression — la brancher sur les étapes donne un feedback utile pour les verbatims longs.

**Affichage de la cohérence Halliday dans la revue.** Si l'Option B (colonnes `halliday_note`, `halliday_ok`) est retenue, `mission_tab_interpretations.py` peut afficher un indicateur visuel (icône vert/orange) sur chaque extrait. Les extraits à `halliday_ok: false` signalent au consultant qu'une vérification s'impose.

### Ce qui n'est PAS recommandé

Les DOSSIER v1 et v2 proposaient une interface "par étapes" avec des boutons "Valider et passer à l'étape suivante". Cette approche est écartée pour les raisons suivantes :

- Elle alourdit massivement l'UX pour un gain marginal : le consultant n'a pas besoin de valider la segmentation avant de voir les interprétations
- Le pipeline automatique (3 appels enchaînés) + la revue post-analyse dans l'onglet existant couvrent le même besoin avec moins de friction
- La revue étape par étape n'apporte de valeur que si les erreurs de segmentation sont fréquentes — ce qui doit être vérifié empiriquement avant d'investir dans l'interface

---

## 6. Ce que cette approche résout et ce qu'elle ne résout pas

### Problèmes résolus

- **Raisonnement Halliday explicite** : rendu obligatoire et auditable à l'Étape 2
- **Traçabilité partielle** : on sait à quelle étape une erreur a été introduite
- **Qualité de l'interprétation** : le LLM se concentre sur une seule tâche à l'Étape 3, ce qui améliore la profondeur analytique
- **Couverture du verbatim** : tous les passages sont segmentés, pas seulement les 3-8 que le modèle juge significatifs
- **Retry ciblé** : si l'Étape 3 échoue (timeout, JSON malformé), les blocs et capacités sont déjà persistés — on peut relancer uniquement l'interprétation

### Problèmes non résolus

- **Hallucinations de capacité** : l'Étape 2 réduit le risque mais ne l'élimine pas. Les 18 capacités restent un espace de décision large pour le modèle.
- **Qualité du modèle local** : si Ollama tourne avec un modèle insuffisant, aucune décomposition en étapes ne compensera des associations capacité/registre incorrectes. Le système prompt `system_01.txt` continue à jouer un rôle critique.
- **Verbatims multilingues ou ambigus** : hors scope de cette analyse.
- **Couverture totale vs sélectivité** : segmenter tout le verbatim peut produire des blocs peu informatifs (généralités, politesses). L'Étape 1 doit être calibrée pour filtrer le méta-discours sans éliminer de contenu utile.

---

## 7. Risques de mise en œuvre

**Régression sur verbatims courts.** Si le verbatim ne comporte que 2-3 passages significatifs, l'approche actuelle (1 appel) est plus efficace que 3 appels séquentiels. Une heuristique simple peut gérer cela : si le verbatim fait moins de N mots (à calibrer, ex: 300), conserver le prompt monolithique comme fallback.

**Augmentation de latence.** 3 appels séquentiels au lieu d'1 : la latence totale sera de 2 à 3× supérieure. Sur Ollama local avec un modèle de taille moyenne, cela passe de ~5s à ~12-15s pour un verbatim standard. Acceptable si l'utilisateur voit un feedback de progression. Problématique si l'UI reste bloquée sans indicateur.

**Cohérence JSON entre étapes.** L'Étape 2 reçoit les blocs de l'Étape 1 et doit les référencer par `block_id`. Si l'Étape 1 retourne un JSON mal structuré, l'Étape 2 échoue. Le parser existant (`_parse_extracts_response`) devra être adapté ou cloné pour chaque format de sortie. Les fallbacks regex actuels restent pertinents.

**Dépendance séquentielle forte.** Si l'Étape 2 produit `capacity_id: null` pour un bloc (ambiguïté Halliday), l'Étape 3 doit soit ignorer ce bloc soit le traiter comme "non classé". Ce cas doit être explicitement géré dans le code, pas laissé au LLM.

---

## 8. Recommandation

### Ce qui est recommandé

Implémenter l'approche itérative en **3 étapes batch** (1 appel Ollama par étape) dans `ai_analyze.py`, avec :

1. Un nouveau prompt `segment_verbatim.txt` (Étape 1)
2. Un nouveau prompt `identify_capacity.txt` (Étape 2) utilisant `halliday_rules.json`
3. Un prompt `interpret_extract.txt` (Étape 3) remplaçant `analyze_verbatim.txt`

La fonction publique `analyze_verbatim()` conserve sa signature externe — elle retourne toujours une liste d'`AnalyzedExtract`. L'itération est interne. L'`_AnalyzeWorker` émet des signaux de progression intermédiaires.

La migration de schéma (Option B : colonnes `halliday_note` + `halliday_ok` sur `Extract`) est recommandée pour porter l'information Halliday jusqu'à l'UI.

### Ce qui est déconseillé dans l'immédiat

- Interface de validation étape par étape : surcharge UX sans bénéfice démontré
- Appels LLM par bloc (N appels à l'Étape 2) : latence inacceptable sans infrastructure parallèle
- Parallélisation avec `ThreadPoolExecutor` : complexifie le code pour un gain limité sur Ollama local qui est de toute façon monothread côté inférence
- Remplacement du modèle ou du backend (graph RAG, agents spécialisés) : hors scope et hors stack

### Ordre de réalisation

1. Rédiger et tester les 3 nouveaux prompts sur des verbatims exemples (avant toute modification du code)
2. Archiver `analyze_verbatim.txt` dans `prompt/versions/`
3. Modifier `ai_analyze.py` pour implémenter le pipeline 3-étapes
4. Ajouter la migration de schéma dans `database.py`
5. Adapter `mission_tab_interpretations.py` pour afficher l'indicateur Halliday
6. Mettre à jour les tests dans `test_mission_crud.py`

---

## Annexe — Données disponibles au moment de chaque appel Ollama

| Étape | Données disponibles en entrée | Ce que le LLM ne doit PAS recevoir |
|---|---|---|
| 1 — Segmentation | Verbatim brut, nom/rôle sujet, level_code | Liste des 18 capacités, échelles de maturité |
| 2 — Identification | Blocs de l'Étape 1, liste des 18 capacités + définitions courtes, règles Halliday | Texte complet du verbatim, échelles de maturité |
| 3 — Interprétation | Blocs annotés de l'Étape 2 (text + capacity_id), échelle de maturité du level_code | Liste complète des capacités, règles Halliday |

Le fait de **ne pas** injecter toutes les informations à chaque étape est intentionnel. Donner au LLM la liste des 18 capacités pendant l'Étape 3 (interprétation) l'encouragerait à reconsidérer les décisions déjà prises à l'Étape 2 — créant une instabilité non souhaitée.
