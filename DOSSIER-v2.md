# DOSSIER-v2.md – Spécification d'Implémentation : Segmentation Intelligente & Analyse Itérative R6

**Version** : 2.0.0  
**Statut** : Spécification de développement consolidée  
**Date** : Q2 2024  
**Synthèse** : Fusion de la segmentation intelligente (6 approches) avec l'analyse itérative par capacités (4 étapes)

---

## 1. Problématique et Contradiction Centrale

### 1.1. Double Défi Technique

L'analyse de verbatims d'entretiens longs (6 000–9 000 mots) pose une **tension irréductible** :

> **Plus on sollicite l'intelligence générative du LLM pour comprendre le sens, plus on risque qu'il altère le texte. Plus on contraint mécaniquement le LLM pour protéger le texte, plus on bride son intelligence sémantique.**

**Contraintes non négociables** :
- **Citation littérale** : Aucune réécriture, aucune correction orthographique silencieuse
- **Exhaustivité** : Aucun passage omis ou agrégé de façon trompeuse
- **Classification typologique** : Chaque bloc qualifié selon taxonomie R6
- **Exclusion méta-discours** : Questions du consultant marquées `irrelevant: true`

---

## 2. Architecture de Déploiement : Solutions Hybrides

### 2.1. Stack Technique Consolidée

| Composant | Technologie | Version | Usage |
|-----------|-------------|---------|-------|
| **Langage** | Python | 3.11+ | Core logic |
| **Segmentation** | spaCy + LLM | 3.7.x | Détection frontières sémantiques |
| **Vectorisation** | text-embedding-3-small | API | Embeddings pour clustering |
| **LLM rapide** | Llama 3 | `llama3:70b` | Segmentation & validation Halliday |
| **LLM puissant** | Mistral Large | `mistral-large-3:675b-cloud` | Classification & interprétation |
| **Orchestration** | LangChain | 0.1.x | Gestion agents, callbacks |
| **Workflow** | Prefect | 2.x | Orchéstration avec retries |
| **Cache** | Redis | 7.2+ | Résultats intermédiaires |
| **Vector DB** | ChromaDB | 0.5+ | Stockage embeddings R6 (futur) |

---

## 3. Méthodes de Segmentation : Catalogue d'Approches

### 3.1. Approche 1 : Sentence-ID Clustering (Recommandée pour MVP)

**Principe** : LLM manipule uniquement des indices, code reconstruit les blocs.

```python
# Pipeline Sentence-ID
Verbatim source
    ↓ [spaCy tokenization]
Liste de phrases numérotées : S_001 "..." | S_002 "..." | ...
    ↓ [LLM — prompt regroupement thématique]
JSON : { start_id: "S_001", end_id: "S_008", theme: "...", type: "observable", irrelevant: false }
    ↓ [Code — jointure]
Bloc avec citation littérale garantie
```

**Avantages** : Intégrité citation absolue, traçabilité parfaite, reproductible.  
**Limites** : Tokenisation imparfaite sur transcriptions orales, intelligence sémantique plafonnée par granularité phrase.  
**Coût** : 1 appel LLM par verbatim.  
**Seuil** : Recommandé pour verbatims < 200 phrases.

### 3.2. Approche 2 : Segmentation par Tours de Parole

**Principe** : Changer de locuteur = frontière sémantique forte.

```python
# Flux
[CONSULTANT] → irrelevant: true (sans LLM)
[INTERVIEWÉ] → Envoi individuel au LLM pour sous-segmentation
```

**Avantages** : Robuste attribution, coût réduit (pas de LLM sur consultant), contexte contrôlé.  
**Limites** : Longs monologues déstructurés nécessitent sous-segmentation complexe.  
**Coût** : 1 appel LLM par prise de parole interviewé.

### 3.3. Approche 3 : Embedding + Clustering Séquentiel

**Principe** : Similarité cosinus détecte frontières, LLM ne classifie qu'en aval.

```python
# Pipeline
Phrases tokenisées → Embeddings → Détection chutes de similarité → Frontières
```

**Avantages** : Découpage objectif, citation garantie 100%, compatible LLM contexte court.  
**Limites** : Embeddings mesurent proximité lexicale, pas cohérence discursive profonde.  
**Coût** : 2 modèles (embedding + LLM), calibrage seuil critique.

### 3.4. Approche 4 : Fenêtre Glissante avec Chevauchement

**Principe** : Tranches de 1000 mots avec recouvrement 200 mots.

```python
# Exemple
Fenêtre 1 : mots 1–1000 → LLM → JSON partiel
Fenêtre 2 : mots 801–1800 → LLM → JSON partiel
↓ [Fusion dé-duplication]
JSON consolidé
```

**Avantages** : Gère verbatims de longueur arbitraire, compatible tous modèles.  
**Limites** : Coût ×1.4 (chevauchements), dé-duplication non triviale, intelligence dégradée aux jointures.  
**Coût** : 2-3 appels LLM par verbatim.

### 3.5. Approach 5 : Injection Globale sur Grand Contexte

**Principe** : Verbatim complet en un appel (Gemini 2.0 Flash, Claude 3.7, GPT-4.1).

```python
# Stratégie
Verbatim (~10k tokens) → Prompt système + few-shot → JSON complet
↓ [Vérification fuzzy matching]
Validation citation
```

**Avantages** : Contexte global → intelligence maximale, anaphores résolues, cohérence labels, architecture minimale.  
**Limites** : Risque omission silencieuse, fuzzy matching obligatoire, coût modèle premium élevé.  
**Coût** : 1 appel premium (~0.03€/1k tokens).

### 3.6. Approche 6 : Double Passe Rupture + Classification

**Principe** : Dissocier "où couper" (passe 1) de "comment qualifier" (passe 2).

```python
# Pipeline
Passe 1 (LLM léger) : Insertion ||BREAK|| aux ruptures thématiques
↓ [Split code]
Liste de blocs avec texte exact (citation garantie)
Passe 2 (LLM précis) : Classification par bloc
```

**Avantages** : Séparation responsabilités propre et débogable, citation garantie.  
**Limites** : Deux séries d'appels API, logique de dé-duplication complexe.  
**Coût** : 1 appel léger + N appels parallèles.

---

## 4. Taxonomie Opératoire : Classification des Blocs

### 4.1. Définitions et Indicateurs Linguistiques

| Type | Définition | Indicateurs Clés | Capacité R6 Visée |
|------|------------|------------------|-------------------|
| **observable** | Action, comportement, décision concrète observable | Verbes d'action au passé composé, sujet individuel | I (Individual) |
| **organisationnel** | Description de processus, règles, structures | Verbes d'état, sujet collectif (nous, équipe) | O (Organizational) |
| **stratégique** | Jugement, projection, posture, vision | Verbes modaux (devrait, pourrait), futur, conditionnel | S (Strategic) |
| **meta** | Commentaire sur l'entretien, question rhétorique | "je dirais que...", "en fait..." | irrelevant |

### 4.2. Règles d'Arbitrage

1. **Ambiguïté S/O** : Si sujet = "nous" mais verbe d'action → privilégier **organisationnel**
2. **Ambiguïté O/S** : Si description processus + jugement de valeur → créer **deux blocs séparés**
3. **Méta-discours** : Toute phrase auto-référentielle → marquer `irrelevant: true`

---

## 5. Architecture de Production Recommandée

### 5.1. Hybrid Split/Tag avec Sentence-ID (Approche 6 + 1)

**Pourquoi cette combinaison ?**  
- Approche 1 garantit citation littérale  
- Approche 6 maximise intelligence sémantique  
- **Phase 1** : Double passe détecte frontières sémantiques  
- **Phase 2** : Sentence-ID assure reproductibilité

```python
# Pipeline complet recommandé

# === PHASE 1 : SEGMENTATION INTELLIGENTE ===
def segmenter_verbatim_hybride(verbatim: str) -> List[SemanticBlock]:
    # 1. Parser locuteurs (Approche 2)
    repliques = parser_tours_de_parole(verbatim)
    
    blocks = []
    for replique in repliques:
        if replique.locuteur == "consultant":
            blocks.append(SemanticBlock(
                block_id=f"meta_{replique.id}",
                context="Méta-discours consultant",
                sentences=replique.sentences,
                type_contenu="meta",
                irrelevant=True
            ))
        else:
            # 2. Double passe (Approche 6)
            # Passe 1 : Insertion marqueurs ||BREAK||
            text_with_breaks = llm_detect_breaks(replique.text)
            
            # Passe 2 : Extraction blocs
            raw_blocks = text_with_breaks.split("||BREAK||")
            
            # 3. Sentence-ID (Approche 1)
            for i, raw_block in enumerate(raw_blocks):
                sentences = spacy_tokenize(raw_block)
                blocks.append(SemanticBlock(
                    block_id=f"{replique.id}_{i}",
                    context=llm_generate_context(raw_block),  # LLM léger
                    sentences=sentences,
                    start_position=verbatim.find(sentences[0]),
                    end_position=verbatim.find(sentences[-1]) + len(sentences[-1]),
                    word_count=sum(len(s.split()) for s in sentences),
                    type_contenu="observable",  # À valider en Phase 2
                    irrelevant=False
                ))
    
    return blocks

# === PHASE 2 : ANALYSE ITÉRATIVE PAR CAPACITÉS ===
def analyser_bloc_iteratif(block: SemanticBlock, level_code: str) -> AnalyzedBlock:
    # Étape 1 : Identification capacité (déjà implémentée dans DOSSIER.md)
    capacity = identifier_capacite(block, level_code)
    
    # Étape 2 : Validation Halliday
    validation = valider_niveau(block, capacity.selected_capacity)
    
    # Étape 3 : Interprétation finale
    interpretation = interpreter_bloc(block, capacity.selected_capacity, validation.level_validé)
    
    return AnalyzedBlock(
        block=block,
        capacity=capacity,
        validation=validation,
        interpretation=interpretation,
        aggregate_confidence=capacity.final_confidence * validation.confidence * interpretation.confidence_interpretation
    )
```

---

## 6. Ingénierie du Prompt : Leviers Critiques

### 6.1. Prompt de Segmentation (Phase 1)

**Fichier** : `segmenter_hybrid.txt`

```jinja
{% raw %}
Tu es un expert en analyse de discours. Segmentes les réponses de l'interviewé en blocs sémantiques COHÉRENTS.

**Tâche** :
1. Identifier les CHANGEMENTS DE REGISTRE (fait → jugement → projection)
2. Insérer le marqueur exact `||BREAK||` à chaque rupture
3. Produire un résumé de 10 mots pour chaque bloc

**Règles** :
- UN BLOC = UN thème, UN registre
- Ne pas couper au milieu d'une phrase
- Ignorer les "euh", "ben", les fausses reprises
- Conserver la formulation exacte

**Exemple** :
Entrée : "J'hésitais entre les fournisseurs ||BREAK|| J'ai fait un tableau comparatif ||BREAK|| J'ai choisi le plus cher mais fiable."
Sortie : 
```json
{
  "blocs": [
    {
      "summary": "Hésitation entre fournisseurs",
      "type": "observable",
      "sentences": ["J'hésitais entre les fournisseurs."]
    },
    {
      "summary": "Processus de décision rationnel",
      "type": "observable",
      "sentences": ["J'ai fait un tableau comparatif."]
    },
    {
      "summary": "Choix qualité sur coût",
      "type": "strategique",
      "sentences": ["J'ai choisi le plus cher mais fiable."]
    }
  ]
}
```

**Texte à segmenter** :
{{ texte_interviewe }}
{% endraw %}
```

### 6.2. Prompts Phase 2 (Analyse Itérative)

**Identifier capacité** : Utiliser `identifier_capacite.txt` du DOSSIER.md (inchangé)  
**Valider niveau** : Utiliser `valider_niveau.txt` du DOSSIER.md (inchangé)  
**Interpréter bloc** : Utiliser `interpreter_bloc.txt` du DOSSIER.md (inchangé)

---

## 7. Métriques de Qualité Professionnelle

### 7.1. KPIs par Phase

| Phase | Métrique | Seuil Actuel | Seuil Cible | Méthode Mesure |
|-------|----------|--------------|-------------|----------------|
| **Segmentation** | Précision frontières | 65% | 85% | Audit manuel sur 100 blocs |
| **Segmentation** | Citation intègre | 92% | 100% | Fuzzy matching |
| **Classification** | Accords inter-juges | 0.68 | 0.85 | Cohen's kappa |
| **Capacité** | Précision capacité | 72% | 88% | Audit manuel |
| **Halliday** | Conformité | 65% | 95% | Test inversion |
| **Interprétation** | Cohérence S-O-I | Non mesuré | 90% | Détection contradictions |
| **Global** | Temps par verbatim | 5s | 8s | Benchmark perf |

### 7.2. Tableau de Bord de Qualité

```python
# r6_navigator/services/quality_dashboard.py

class QualityDashboard:
    def __init__(self, session_factory):
        self.session = session_factory
    
    def get_batch_metrics(self, mission_id: int) -> dict:
        """Retourne métriques pour tous les verbatims d'une mission"""
        
        analyses = self.session.query(VerbatimAnalysis).join(Verbatim).join(Interview).filter(
            Interview.mission_id == mission_id
        ).all()
        
        return {
            "total_verbatims": len(analyses),
            "avg_confidence": sum(a.total_confidence for a in analyses) / len(analyses),
            "needs_review_count": sum(1 for a in analyses if a.needs_review),
            "segmentation_accuracy": self._calculate_segmentation_accuracy(analyses),
            "halliday_compliance": self._calculate_halliday_compliance(analyses),
            "capacity_precision": self._calculate_capacity_precision(analyses)
        }
    
    def generate_quality_report(self, mission_id: int) -> str:
        """Génère rapport PDF pour client"""
        # TODO: Implémenter avec python-docx
        pass
```

---

## 8. Plan d'Implémentation par Phase

### 8.1. Phase 1 (Sprint 1-2) : MVP Production

**Livrables** :
- ✅ Implémentation Approche 6 (Double passe) + Approche 1 (Sentence-ID)
- ✅ Prompts segmentation et analyse itérative
- ✅ Modèles Pydantic complets
- ✅ Cache Redis basique
- ✅ UI `IterativeAnalysisWindow` pour review

**Critères de succès** :
- Segmentation citation intègre : 100%
- Précision capacité : +15% vs actuel
- Temps analyse < 10s/verbatim
- Pas de régression sur cas simples

### 8.2. Phase 2 (Sprint 3-4) : Excellence Multi-Agent

**Livrables** :
- Architecture LangChain avec 3 agents (Segmenteur, Identifieur, Validateur, Superviseur)
- Few-shot learning (3 exemples/capacité critique)
- Parallélisation des étapes avec Prefect
- Dashboard qualité

**Critères de succès** :
- Précision capacité : 88%
- Conformité Halliday : 95%
- Latency : 4s/bloc
- Satisfaction consultant > 4.0/5

### 8.3. Phase 3 (Sprint 5-6) : Auditabilité Graph

**Livrables** :
- Graphe de connaissances R6 v1.0 dans ChromaDB
- Recherche vectorielle des capacités candidates
- Intégration graph → agents
- White paper méthodologique

**Critères de succès** :
- Réduction hallucinations : 70%
- Possibilité audit externe
- Prêt certifications

---

## 9. Conclusion et Recommandation Stratégique

### 9.1. Synthèse

L'**approche hybride Double Passe + Sentence-ID** résout la contradiction centrale :  
- **Phase 1** : LLM détecte ruptures sémantiques (intelligence)  
- **Code** : Garantit citation littérale (protection)  
- **Phase 2** : Analyse itérative par capacités (qualité diagnostic)

### 9.2. Recommandation

**Adopter la Phase 1 comme standard production dès Q2 2024**, avec un budget de **5 jours de développement** et **2h/semaine de maintenance** pour affiner les prompts.

**Allouer 15 jours supplémentaires pour Phase 2** si le KPI "précision capacité > 88%" est requis pour différenciation concurrentielle.

**Reporter Phase 3** à Q4 2024, conditionné à l'obtention de contrats nécessitant audit externe.

### 9.3. Prochaine Action

**Créer Pull Request** avec :
- `IterativeAnalyzer` complet (Phase 1)
- Suite de test `test_quality_benchmark.py` (50 cas annotés)
- Documentation prompts et métriques

**Reviewer** : Doit valider citation intègre sur 10 verbatims aléatoires.

---

**Fin DOSSIER-v2.md**
