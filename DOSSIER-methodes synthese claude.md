# Note de synthèse — Segmentation intelligente et analyse automatisée de verbatims longs par LLM

**Domaine :** Traitement automatique du langage naturel appliqué à l'analyse qualitative  
**Contexte :** Entretiens de consultants — verbatims d'une heure, interlocuteurs identifiés  
**Objet :** Comparaison des approches de segmentation sémantique et de classification typologique  
**Version :** 1.0

---

## Sommaire

1. [[## 1. Problématique et enjeux]]
2. [Cadre conceptuel : ce que signifie "segmenter intelligemment"](#2-cadre-conceptuel)
3. [Étape préliminaire universelle : le découpage par tours de parole](#3-étape-préliminaire-universelle)
4. [Catalogue des approches de segmentation](#4-catalogue-des-approches)
5. [Maximiser l'intelligence sémantique : architectures avancées](#5-maximiser-lintelligence-sémantique)
6. [Ingénierie du prompt : leviers critiques](#6-ingénierie-du-prompt)
7. [Taxonomie opératoire](#7-taxonomie-opératoire)
8. [Tableaux comparatifs de synthèse](#8-tableaux-comparatifs)
9. [Recommandations architecturales](#9-recommandations-architecturales)
10. [Conclusion](#10-conclusion)

---

## 1. Problématique et enjeux

### 1.1 Contexte opérationnel

L'analyse de verbatims d'entretiens longs (environ une heure de parole, soit 6 000 à 9 000 mots transcrits) pose un double problème technique et sémantique :

- **Problème technique :** les LLM ne peuvent pas être utilisés naïvement sur des textes de cette taille sans risquer des omissions, des paraphrases silencieuses ou des hallucinations portant sur le texte source.
- **Problème sémantique :** un entretien n'est pas un texte homogène. L'interviewé alterne entre des registres discursifs différents (description factuelle, jugement de valeur, projection, métadiscours) sans signaux syntaxiques clairs de transition.

### 1.2 Contraintes non négociables

| Contrainte | Implication technique |
|---|---|
| **Citation littérale** | Le champ `quote` du bloc doit être une copie caractère par caractère du texte source — aucune réécriture, aucune correction orthographique silencieuse |
| **Exhaustivité** | Aucun passage du discours de l'interviewé ne doit être omis ou agrégé de façon trompeuse |
| **Classification typologique** | Chaque bloc doit être qualifié selon une taxonomie définie : observable comportemental, description organisationnelle, posture stratégique |
| **Exclusion du méta-discours** | Les questions du consultant et les éléments non substantiels sont marqués `irrelevant: true` et exclus des étapes analytiques suivantes |

### 1.3 Tension centrale

La tension fondamentale de ce problème est la suivante :

> **Plus on sollicite l'intelligence générative du LLM pour comprendre le sens, plus on risque qu'il altère le texte. Plus on contraint mécaniquement le LLM pour protéger le texte, plus on bride son intelligence sémantique.**

Toutes les approches décrites dans ce document sont des réponses différentes à cette tension.

---

## 2. Cadre conceptuel

### 2.1 Ce que "segmenter intelligemment" signifie réellement

Un découpage sémantiquement intelligent va bien au-delà du *chunking* mécanique utilisé dans les pipelines RAG. Il s'agit de produire des blocs qui respectent la cohérence discursive plutôt que la taille ou la ponctuation.

Concrètement, cela implique de :

- **Détecter les changements de registre** : un interviewé peut passer d'une description factuelle à un jugement de valeur au milieu d'une même phrase, sans transition explicite.
- **Reconnaître les thèmes imbriqués** : un même passage peut contenir simultanément un observable comportemental et une posture stratégique — il faut savoir si on les sépare en deux blocs ou si on choisit le type dominant.
- **Capturer les fils rouges transversaux** : une préoccupation récurrente peut être formulée différemment à plusieurs moments de l'entretien ; le découpage doit permettre de les relier en post-traitement.
- **Identifier les non-dits et glissements discursifs** : une description d'apparence neutre peut être une critique voilée ; une question rhétorique peut être une posture stratégique déguisée.

### 2.2 Les deux tâches cognitives à dissocier

La segmentation intelligente implique deux opérations fondamentalement différentes qu'il est utile de distinguer, même quand elles sont réalisées dans un même appel :

| Tâche | Question | Niveau cognitif | Risque si mal gérée |
|---|---|---|---|
| **Segmentation** | *Où couper ?* | Discursif, pragmatique | Blocs trop larges (thèmes mélangés) ou trop fins (sens fragmenté) |
| **Classification** | *Comment qualifier ?* | Analytique, typologique | Contresens sur le type, confusion observable/posture |

La plupart des architectures avancées dissocient explicitement ces deux tâches, soit en deux passes LLM, soit en séparant la couche algorithmique de la couche LLM.

---

## 3. Étape préliminaire universelle

### 3.1 Le découpage par tours de parole

**Toutes les approches convergent sur un point :** avant tout traitement LLM, le verbatim doit être structuré mécaniquement par locuteur.

Cette étape préliminaire est réalisée par le code (regex ou parsing de balises de locuteur) et produit deux flux distincts :

```
[CONSULTANT] → irrelevant: true, type: méta-discours — sans appel LLM
[INTERVIEWÉ]  → flux à traiter par les approches décrites ci-dessous
```

**Bénéfices de cette étape :**
- Réduit la charge cognitive du modèle en éliminant le bruit avant même le premier appel.
- Sécurise l'attribution des propos — aucun risque de confondre une relance du consultant avec une posture de l'interviewé.
- Diminue le volume de tokens traités et donc le coût.

### 3.2 Structure de sortie cible

Quelle que soit l'approche retenue, la structure JSON cible par bloc est la suivante :

```json
{
  "bloc_id": "B_042",
  "locuteur": "interviewé",
  "quote": "texte exact, copie littérale du verbatim source",
  "theme": "Résumé en une phrase du sujet abordé",
  "type_contenu": "observable | organisationnel | strategique | meta",
  "irrelevant": false,
  "start_id": "S_108",
  "end_id": "S_114"
}
```

Le champ `start_id` / `end_id` n'est pertinent que pour l'Approche 1 (Sentence-ID). Le champ `analyse_intention` (voir section 5) est optionnel mais fortement recommandé pour maximiser la qualité de la classification.

---

## 4. Catalogue des approches de segmentation

### Approche 1 — Sentence-ID Clustering (indexation + reconstruction)

**Principe :** Interdire au LLM de toucher le texte. Le LLM ne manipule que des index ; le code reconstruit les blocs.

**Pipeline détaillé :**

```
Verbatim source
    ↓ [Code — spaCy / NLTK]
Liste de phrases numérotées : S_001 "..." | S_002 "..." | ...
    ↓ [LLM — prompt de regroupement thématique]
JSON : { start_id: "S_001", end_id: "S_008", theme: "...", type: "...", irrelevant: false }
    ↓ [Code — reconstruction par jointure]
Bloc avec citation littérale garantie
```

**Avantages :**
- Intégrité de la citation : **absolue**. Le LLM ne réécrit rien.
- Traçabilité parfaite — chaque bloc est ancré dans le fichier source par ses identifiants de phrases.
- Granularité fine possible.

**Limites :**
- La tokenisation en phrases est elle-même imparfaite sur des transcriptions orales (phrases inachevées, chevauchements, faux départs).
- L'intelligence sémantique est **plafonnée par la granularité de la phrase** : si le LLM ne peut regrouper que des phrases entières, il ne peut pas couper à l'intérieur d'une phrase qui change de registre.
- Code de pré/post-traitement à développer et maintenir.

---

### Approche 2 — Segmentation par tours de parole (heuristique structurelle)

**Principe :** Exploiter la structure naturelle de l'entretien. Le changement de locuteur est la frontière sémantique la plus forte et la plus fiable.

**Pipeline détaillé :**

```
Verbatim structuré par locuteur
    ↓ [Code — parsing]
Répliques du consultant → irrelevant: true (sans appel LLM)
Réponses de l'interviewé → envoi individuel au LLM
    ↓ [LLM — prompt de sous-segmentation + classification]
JSON par prise de parole, avec subdivision si plusieurs thèmes détectés
```

**Avantages :**
- Très robuste sur l'attribution des propos.
- Fenêtre de contexte par appel restreinte → moins de risque de dérive.
- Les répliques du consultant sont traitées sans coût LLM.

**Limites :**
- Les longs monologues déstructurés (l'interviewé parle 10 minutes sans interruption en changeant de sujet 4 fois) nécessitent une sous-segmentation complexe.
- Le LLM ne voit qu'une prise de parole à la fois — il peut manquer des fils conducteurs transversaux à l'entretien.

---

### Approche 3 — Embedding + clustering séquentiel (segmentation vectorielle)

**Principe :** Remplacer le jugement LLM sur les frontières par un calcul de similarité cosinus entre phrases adjacentes. Le LLM n'intervient qu'en aval pour la classification.

**Pipeline détaillé :**

```
Phrases tokenisées
    ↓ [Modèle d'embedding — text-embedding-3-small, nomic-embed, etc.]
Vecteurs sémantiques par phrase
    ↓ [Calcul de similarité cosinus entre phrases consécutives]
Détection des chutes de similarité → frontières de blocs
    ↓ [LLM — prompt de classification par bloc]
JSON annoté
```

**Avantages :**
- Découpage objectivement basé sur le sens, sans dépendre d'un prompt.
- Reproductible et auditable (même seuil = mêmes frontières).
- Citation littérale garantie à 100 % — le LLM ne touche pas le texte de segmentation.
- Compatible avec des modèles LLM à contexte court (petits blocs envoyés individuellement).

**Limites :**
- Les embeddings mesurent la **proximité lexicale**, pas la cohérence discursive profonde. Deux phrases sur des sujets différents mais avec des mots communs peuvent être perçues comme proches.
- Sensible au calibrage du seuil de rupture — sur-segmentation ou sous-segmentation possible.
- Architecture complexe : deux modèles à gérer (embedding + génération).

---

### Approche 4 — Fenêtre glissante avec chevauchement (prompting itératif)

**Principe :** Traiter le verbatim par tranches séquentielles qui se recouvrent, pour ne pas couper de blocs thématiques en plein milieu.

**Pipeline détaillé :**

```
Verbatim complet
    ↓ [Code — découpage en fenêtres de ~1 000 mots, recouvrement de ~200 mots]
Fenêtre 1 : mots 1–1000 → LLM → JSON partiel
Fenêtre 2 : mots 801–1800 → LLM → JSON partiel
...
    ↓ [Code — fusion et dé-duplication des blocs dans les zones de chevauchement]
JSON consolidé
```

**Avantages :**
- Traite des verbatims de longueur arbitraire, indépendamment de la fenêtre du modèle.
- Compatible avec tous les modèles, y compris les plus anciens ou les moins coûteux.

**Limites :**
- Coût en tokens élevé (les zones de chevauchement sont traitées deux fois).
- La logique de dé-duplication est non triviale et source d'erreurs aux jonctions.
- L'intelligence sémantique est **dégradée aux jointures** : un bloc thématique qui chevauche deux fenêtres peut être mal qualifié dans l'une ou l'autre.

---

### Approche 5 — Injection globale sur modèle à grand contexte (zero-shot)

**Principe :** Passer l'intégralité du verbatim en un seul appel sur un modèle à fenêtre étendue, en exigeant une sortie JSON structurée.

**Modèles compatibles (2025–2026) :** Gemini 2.0 Flash (fenêtre 1M tokens), Claude 3.7 Sonnet (200k tokens), GPT-4.1 (1M tokens).

**Pipeline détaillé :**

```
Verbatim complet (~7 000 mots ≈ ~10 000 tokens)
    ↓ [Prompt système : taxonomie + schéma JSON + exemples few-shot]
LLM — un seul appel
    ↓
JSON brut avec tous les blocs
    ↓ [Code — vérification fuzzy matching (rapidfuzz) pour chaque quote]
JSON validé + rapport d'anomalies
```

**Avantages :**
- Architecture minimale (un seul appel API).
- Le LLM dispose du contexte global → **intelligence sémantique maximale** : résolution des anaphores, compréhension de l'arc narratif, détection des fils conducteurs transversaux.
- Cohérence des labels thématiques sur l'ensemble de l'entretien.

**Limites :**
- Risque d'omission silencieuse ou de paraphrase sur de très longs textes.
- La vérification par fuzzy matching est **obligatoire**, pas optionnelle.
- Coût par appel élevé sur les modèles premium.

---

### Approche 6 — Double passe : rupture puis classification (hybrid split/tag)

**Principe :** Dissocier explicitement les deux tâches cognitives — *où couper* (passe 1) et *comment qualifier* (passe 2).

**Pipeline détaillé :**

```
Verbatim de l'interviewé
    ↓ [Passe 1 — LLM léger : insertion de ||BREAK|| aux ruptures thématiques]
Texte balisé : "... fin de bloc A ||BREAK|| début de bloc B ..."
    ↓ [Code — split sur ||BREAK||]
Liste de blocs avec texte exact (citation garantie)
    ↓ [Passe 2 — LLM précis : classification par bloc, JSON strict]
JSON final annoté
```

**Avantages :**
- Séparation des responsabilités propre et débogable.
- La passe 1 peut utiliser un modèle léger/rapide (GPT-4o mini, Haiku) pour réduire le coût.
- La passe 2 peut être parallélisée (tous les blocs envoyés simultanément).
- La citation est garantie : le code extrait les blocs sans réécriture LLM.

**Limites :**
- Deux séries d'appels API.
- La passe 1 doit être cadrée par un prompt strict pour éviter la sur-segmentation.
- Le LLM de la passe 2 ne voit qu'un bloc isolé — risque de contresens sans contexte global.

---

## 5. Maximiser l'intelligence sémantique

### 5.1 Ce que cela implique réellement

Maximiser l'intelligence sémantique signifie permettre au modèle de :

1. **Résoudre les anaphores** ("ce projet", "cette décision", "eux") en connaissant le contexte antérieur.
2. **Détecter les changements de registre implicites** — passage d'un fait à une opinion sans marqueur linguistique.
3. **Identifier les tensions et contradictions** entre différentes postures exprimées à des moments séparés.
4. **Reconnaître l'ironie, la critique voilée et les euphémismes** — une description de processus peut être une critique stratégique formulée prudemment.
5. **Tracer les fils rouges thématiques** qui traversent l'entretien.

Ces capacités nécessitent impérativement que **le modèle ait vu l'ensemble du texte** — ou dispose d'une mémoire du contexte accumulé.

### 5.2 Architecture cible : injection globale + Chain of Thought + réconciliation algorithmique

C'est l'architecture qui combine le plus haut niveau d'intelligence sémantique avec un garde-fou d'intégrité.

#### Passe 1 — Injection du contexte global et segmentation par raisonnement explicite

```
PROMPT SYSTÈME :
"Tu es un analyste expert en discours organisationnel.
 Le document ci-dessous est l'intégralité d'un entretien.
 Lis-le en entier avant de commencer. Ne segmente pas encore.
 [VERBATIM COMPLET]"

PROMPT UTILISATEUR :
"Maintenant, relis séquentiellement le discours de l'interviewé.
 À chaque changement de sujet ou de registre discursif, explique
 brièvement la transition sémantique en une phrase, puis insère
 la balise [SPLIT].
 Format : [JUSTIFICATION DE RUPTURE] [SPLIT] [texte suivant...]"
```

**Pourquoi le Chain of Thought améliore la segmentation :** obliger le LLM à justifier chaque frontière avant de la poser l'oblige à mobiliser une compréhension discursive approfondie. Les études sur le Chain of Thought montrent systématiquement une amélioration de la précision sur les tâches de raisonnement complexe.

#### Passe 2 — Classification avec analyse d'intention intercalée

Au lieu de demander directement la catégorie, le schéma JSON intègre un champ de réflexion intermédiaire :

```json
{
  "citation_exacte": "...",
  "analyse_intention": "Explication de ce que l'interviewé cherche à communiquer dans cet extrait, mis en perspective avec le contexte global de l'entretien.",
  "theme": "Résumé du sujet en une phrase",
  "type_contenu": "observable | organisationnel | strategique | meta",
  "irrelevant": false
}
```

**Pourquoi ce champ est décisif :** en forçant le LLM à expliquer l'intention avant de fixer la catégorie, on prévient les contresens classiques :
- Une phrase ironique ne sera pas classée "observable comportemental".
- Une description de processus formulée avec détachement critique ne sera pas classée "description organisationnelle" si l'intention est stratégique.
- Un euphémisme sera reconnu comme tel.

#### Passe 3 — Réconciliation algorithmique (garde-fou d'intégrité)

```python
from rapidfuzz import fuzz, process

def reconcile_quote(llm_quote: str, source_text: str, threshold: int = 90) -> str:
    """
    Recherche dans source_text la sous-chaîne la plus proche de llm_quote.
    Si le score est inférieur au seuil, lève une alerte pour révision manuelle.
    Retourne la citation exacte du texte source.
    """
    # Implémentation par fenêtre glissante sur le texte source
    ...
```

Cette étape **annule toute paraphrase silencieuse** du modèle et garantit que le champ `citation_exacte` est une copie caractère par caractère du verbatim source.

### 5.3 Variante : double passe avec contexte cumulatif

Pour les verbatims qui dépassent la fenêtre du modèle, une variante maintient l'intelligence sémantique sans injection globale :

```
Blocs 1 à N déjà traités → résumé cumulatif ("mémoire de l'entretien")
    +
Texte courant à segmenter
    ↓
Prompt : "Tiens compte du contexte accumulé pour identifier les 
          ruptures et les continuités thématiques."
```

Cette approche simule la connaissance du contexte global en fournissant une mémoire construite progressivement. Elle est moins puissante que l'injection globale (le résumé perd des nuances) mais constitue le meilleur compromis quand la taille du verbatim dépasse la fenêtre disponible.

### 5.4 Variante : embeddings comme filtre de frontières candidates

Les embeddings seuls ont une intelligence sémantique limitée, mais ils peuvent être combinés avec le LLM de façon productive :

1. L'algorithme d'embedding propose des frontières candidates (chutes de similarité cosinus).
2. Le LLM reçoit ces frontières candidates et l'instruction : *"Révise ces frontières si tu estimes qu'une rupture thématique plus pertinente existe à un autre endroit."*

Cela combine la reproductibilité de l'approche algorithmique avec le jugement discursif du LLM.

---

## 6. Ingénierie du prompt

### 6.1 Les trois leviers critiques

#### Levier 1 — Définitions opératoires avec exemples contrastés (few-shot)

Ne pas seulement définir les catégories — montrer des **cas limites annotés**. La distinction entre les types est souvent ténue dans les verbatims réels :

| Énoncé | Type correct | Raison |
|---|---|---|
| *"Je convoque systématiquement mon équipe avant chaque arbitrage."* | Observable comportemental | Verbe d'action + fréquence + description de pratique |
| *"Je crois qu'il faut impliquer l'équipe avant d'arbitrer."* | Posture stratégique | Croyance + prescription normative |
| *"Chez nous, les arbitrages se font en comité de direction."* | Description organisationnelle | Fait structurel, processus institutionnalisé |
| *"On va manquer de temps si on continue comme ça."* | Posture stratégique | Projection, jugement sur la trajectoire |
| *"D'accord, donc vous me dites que..."* | Méta-discours | Reformulation de l'interviewer |

#### Levier 2 — Instruction de sensibilité aux glissements de registre

```
"Un même tour de parole peut contenir plusieurs types discursifs.
 Si l'interviewé passe d'une description factuelle à une opinion
 sans transition explicite, crée deux blocs distincts même si
 la frontière est au milieu d'une phrase continue."
```

#### Levier 3 — Instruction de cohérence globale

```
"Après avoir segmenté, vérifie que des blocs séparés n'adressent
 pas en réalité le même thème sous des formulations différentes.
 Si c'est le cas, attribue-leur le même label thématique pour
 permettre le regroupement en post-traitement."
```

### 6.2 Instruction de protection de l'intégrité

Quelle que soit l'architecture, cette instruction doit figurer dans le prompt système :

```
"RÈGLE ABSOLUE : Le champ 'citation_exacte' doit être une copie
 caractère par caractère du texte source. Tu n'es pas rédacteur.
 Tu ne corriges pas l'orthographe, tu ne reformules pas, tu ne
 complètes pas les phrases inachevées. Si tu ne peux pas extraire
 la citation exacte, signale-le avec le flag 'integrity_warning: true'."
```

---

## 7. Taxonomie opératoire

### 7.1 Définitions et indicateurs linguistiques

| Type | Définition | Indicateurs linguistiques | Exemples typiques |
|---|---|---|---|
| **Observable comportemental** | Ce que la personne fait ou a fait. Actions spécifiques et situées. | Verbes d'action au passé ou présent, circonstances précises (quand, avec qui, comment), description de tâches | *"Chaque lundi matin je fais le point individuel avec chacun de mes chefs de projet."* |
| **Description organisationnelle** | Le contexte statique ou structurel. Faits sur l'environnement. | Verbes d'état, termes institutionnels, descriptions de processus officiels, mentions d'organigrammes ou d'outils | *"Notre SIRH ne permet pas de suivre les compétences au niveau individuel."* |
| **Posture stratégique** | L'opinion, la vision ou l'intention. Ce que la personne croit, projette, juge. | Modaux (devoir, falloir, vouloir), verbes d'opinion (croire, penser, estimer), projections futures, jugements de valeur | *"À mon sens, la priorité devrait être de reconstruire la confiance avant de parler de performance."* |
| **Méta-discours** | Bruit de communication. Ce qui régule l'entretien sans produire de contenu analytique. | Phatiques, reformulations de l'interviewer, questions de relance, digressions logistiques | *"Vous pouvez développer ?"* / *"Hmm, d'accord."* |

### 7.2 Cas limites et règles d'arbitrage

**Règle 1 — Ambiguïté observable / posture :** si l'énoncé décrit une pratique récurrente *et* indique que l'interviewé y croit, créer deux blocs séparés ou choisir le type dominant selon la proportion syntaxique.

**Règle 2 — Description organisationnelle critique :** si une description de processus est formulée avec des marqueurs évaluatifs ("malheureusement", "ce qui pose problème", "on ne peut pas dire que..."), le type dominant devient **posture stratégique**.

**Règle 3 — Ironie et litote :** si le contexte global (connu par injection globale) permet d'identifier une formulation ironique, la classer selon l'intention réelle et non la forme de surface.

---

## 8. Tableaux comparatifs de synthèse

### 8.1 Tableau général des approches

| # | Approche | Intégrité citation | Intelligence sémantique | Complexité technique | Coût tokens | Fenêtre requise | Cas d'usage optimal |
|---|---|---|---|---|---|---|---|
| 1 | Sentence-ID Clustering | ✅✅ Absolue | ✅ Moyenne (plafonnée) | 🔧🔧 Modérée | Moyen | Court | Exigence probatoire, audit |
| 2 | Tours de parole + sous-seg. | ✅✅ Très haute | ✅✅ Élevée | 🔧 Faible | Faible | Court | Entretiens semi-directifs structurés |
| 3 | Embedding + clustering séq. | ✅✅ Absolue | ✅ Moyenne | 🔧🔧🔧 Élevée | Faible | Court | Volumes industriels, reproductibilité |
| 4 | Fenêtre glissante | ✅ Bonne* | ✅ Moyenne* | 🔧🔧 Modérée | Élevé | Court | Modèles sans grand contexte |
| 5 | Injection globale (zero-shot) | ⚠️ À vérifier | ✅✅✅ Maximale | 🔧 Très faible | Élevé | ≥ 128k | Prototypage, analyse qualitative fine |
| 6 | Double passe split/tag | ✅✅ Haute | ✅✅ Élevée | 🔧🔧 Modérée | Moyen | Court à moyen | Pipeline modulaire, optimisation coût |

\* Dégradée aux jonctions de fenêtres / nécessite fuzzy matching

### 8.2 Tableau des architectures avancées pour l'intelligence sémantique maximale

| Étape | Architecture | Méthode | Bénéfice sémantique |
|---|---|---|---|
| 1 | Injection contexte global | Verbatim complet en prompt système (modèle ≥ 128k tokens) | Résolution des anaphores, compréhension de l'arc narratif, cohérence globale des labels |
| 2 | Segmentation par CoT | Insertion de `[SPLIT]` précédée d'une justification explicite de la rupture | Détection des frontières implicites et des glissements de registre invisibles |
| 3 | Classification par intention | Champ `analyse_intention` dans le JSON avant la taxonomie finale | Prévention des contresens (ironie, critique voilée, euphémismes) |
| 4 | Réconciliation algorithmique | Fuzzy matching (rapidfuzz / Levenshtein) entre `citation_exacte` et texte source | Garantie d'intégrité absolue après exploitation maximale du génératif |

### 8.3 Tableau de décision selon les contraintes projet

| Contrainte dominante | Approche recommandée | Justification |
|---|---|---|
| **Intégrité absolue de la citation** (usage légal, audit) | Approche 1 (Sentence-ID) | Zéro réécriture possible — le LLM ne touche pas le texte |
| **Simplicité de déploiement** (prototypage, POC) | Approche 5 (injection globale) | Un seul appel API, architecture minimale |
| **Intelligence sémantique maximale** | Approche 5 augmentée (CoT + réconciliation) | Contexte global + raisonnement explicite + garde-fou algorithmique |
| **Coût maîtrisé sur corpus volumineux** | Approche 6 (double passe) + modèle léger passe 1 | GPT-4o mini ou Haiku pour la segmentation, modèle précis pour la classification |
| **Reproductibilité et auditabilité** | Approche 3 (embeddings) | Frontières mathématiquement fondées, reproductibles avec le même seuil |
| **Entretiens semi-directifs standards** | Approche 2 (tours de parole) | La structure de l'entretien est exploitée comme signal sémantique premier |
| **Verbatims dépassant la fenêtre disponible** | Approche 6 avec contexte cumulatif | Double passe + résumé progressif simulant la mémoire globale |

### 8.4 Tableau de sélection du modèle LLM

| Modèle | Fenêtre contexte | Force | Limite | Usage recommandé |
|---|---|---|---|---|
| Gemini 2.0 Flash | 1M tokens | Contexte massif, coût faible | Paraphrases possibles sur très longs textes | Injection globale d'entretiens entiers |
| Claude 3.7 Sonnet | 200k tokens | Excellente fidélité aux instructions, précision taxonomique | Coût modéré | Passe 2 (classification), prompts complexes few-shot |
| GPT-4.1 | 1M tokens | Structured outputs natifs (JSON strict) | Coût élevé en production | Injection globale + JSON schéma contraint |
| GPT-4o mini / Haiku | 128k tokens | Très faible coût, rapide | Intelligence sémantique limitée | Passe 1 (segmentation légère), chaînes de traitement à volume |
| Modèles locaux (Ollama) | Variable | Coût nul, confidentialité des données | Performance inférieure sur tâches complexes | Expérimentation, données sensibles non exportables |

---

## 9. Recommandations architecturales

### 9.1 Recommandation pour une production analytique de qualité

**Architecture recommandée : Approche 2 + Approche 5 augmentée en combinaison**

```
PHASE 0 — Pré-traitement (code)
    Parsing par tours de parole
    → Répliques consultant : irrelevant: true (sans LLM)
    → Réponses interviewé : flux de traitement

PHASE 1 — Segmentation globale (LLM grand contexte)
    Injection du verbatim complet de l'interviewé
    Prompt Chain of Thought : justification + [SPLIT]
    → Blocs segmentés avec texte exact

PHASE 2 — Classification (LLM précis, en parallèle)
    Envoi de chaque bloc avec contexte global résumé
    Schéma JSON : citation_exacte + analyse_intention + theme + type + irrelevant
    → JSON annoté par bloc

PHASE 3 — Réconciliation algorithmique (code)
    Fuzzy matching de chaque citation_exacte avec le verbatim source
    Seuil : score ≥ 90 → validation automatique
    Score < 90 → alerte + rematch par offset caractère
    → JSON validé

PHASE 4 — Optionnel : synthèse thématique transversale
    Second appel LLM avec l'ensemble des blocs validés
    "Identifie les thèmes récurrents et les tensions entre postures"
    → Rapport thématique de l'entretien
```

### 9.2 Ce qu'il faut éviter

| Anti-pattern | Risque |
|---|---|
| Chunking mécanique par taille fixe (RAG-style) | Découpe des blocs thématiques en plein milieu → incohérence des unités d'analyse |
| Demander directement la catégorie sans définitions opératoires | Taux élevé de contresens sur observable/posture, surtout sur les énoncés ambigus |
| Faire confiance à la citation LLM sans vérification | Paraphrases silencieuses non détectées → données analytiques corrompues |
| Utiliser un seul appel sans few-shot sur des entretiens complexes | Taxonomie incohérente d'un bloc à l'autre |
| Traiter les répliques du consultant avec le même pipeline que l'interviewé | Coût inutile + risque de classement erroné |

---

## 10. Conclusion

### 10.1 Synthèse de la tension centrale

La segmentation intelligente de verbatims longs est fondamentalement un problème de **découplage entre compréhension et preuve**. Le LLM excelle dans la compréhension discursive profonde ; il est structurellement risqué comme garant de la fidélité textuelle. L'architecture optimale confie à chacun ce qu'il fait le mieux :

> **LLM → comprendre, segmenter, qualifier**  
> **Code → extraire, reconstruire, vérifier**

### 10.2 Principe directeur

Si l'intelligence sémantique est la priorité (ce qui est le cas pour une analyse qualitative sérieuse), l'**Approche 5 augmentée** — injection globale + Chain of Thought + champ `analyse_intention` + réconciliation algorithmique — est l'architecture cible. Elle maximise la qualité analytique tout en neutralisant le principal risque des LLM génératifs.

Si la priorité est la **robustesse industrielle** sur un corpus volumineux avec contrainte de coût, l'**Approche 6** (double passe) avec un modèle léger en passe 1 et un modèle précis en passe 2, combinée à l'étape préliminaire de tours de parole, constitue le meilleur compromis.

### 10.3 Condition sine qua non

Quelle que soit l'architecture retenue, **deux éléments sont non négociables** :

1. **Un prompt few-shot soigné** avec des définitions opératoires et des exemples contrastés sur les cas limites de la taxonomie.
2. **Une vérification algorithmique de l'intégrité des citations** (fuzzy matching) en post-traitement — cette étape doit être considérée comme une composante de l'architecture, pas comme une option.

---

*Synthèse réalisée à partir des analyses comparatives Claude/Gemini — IOD Ingénierie — Mars 2026*
