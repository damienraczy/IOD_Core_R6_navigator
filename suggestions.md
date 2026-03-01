# Amélioration de la génération des risques — Analyse et propositions

## 1. Diagnostic du prompt actuel

Le prompt `generate_fiche_risque.txt` demande au LLM de décrire :
- des "signes observables de déficit" (`risk_insufficient`)
- des "signes d'hyperactivation pathologique" (`risk_excessive`)

Le seul ancrage structurel fourni est le contexte Halliday (niveau I/O/S et type de processus).
Le LLM ne sait pas que la capacité qu'il traite est **positionnée dans un treillis relationnel** :
il ne connaît pas son pôle jumeau, ses capacités adjacentes sur l'axe vertical, ni l'objet
stratégique de R6 (transformation, réalignement, transition technologique).

Résultat : le LLM génère des descriptions comportementales génériques, déconnectées de la
logique structurelle. Les risques produits ressemblent à des items de bilan de compétences
standards, pas à des signaux de dysfonction organisationnelle systémique.

---

## 2. Catégories de risques structurels

Les quatre catégories proposées sont toutes pertinentes et directement déductibles des
principes axiomatiques de R6 (`axioms.yml`). Voici leur formulation affinée, plus deux
ajouts :

### 2.1 Déséquilibre polaire (axe horizontal)

Chaque axe porte une tension entre deux pôles complémentaires (a = agentif/stabilisateur,
b = instrumental/transformateur). Ces pôles ne s'annulent pas — ils se régulent mutuellement.

**Déficit** : le pôle jumeau prend toute la charge faute d'ancrage sur ce pôle-ci
→ la tension polarisante disparaît, remplacée par une dérive unilatérale.

**Excès** : ce pôle écrase son jumeau, le rendant inopérant → même résultat, sens inverse.

*Exemple : I1a (Responsabilité) insuffisant → I1b (Innovation) s'emballe sans ancrage ;
I1a excessif → I1b asphyxié, l'organisation se fige.*

### 2.2 Blocage de l'émergence (axe vertical ascendant N → N+1)

Les niveaux supérieurs émergent des inférieurs mais ne s'y réduisent pas. Une défaillance
à N empêche mécaniquement la constitution de la capacité à N+1.

**Déficit** : la capacité de niveau supérieur ne peut pas s'instituer, même si la volonté
stratégique existe — le matériau n'est pas là.

**Excès** : le niveau supérieur est saturé par une émergence bruyante et incontrôlée —
il ne peut plus réguler, il absorbe.

*Exemple : O1b (Enabling Transformation) insuffisant → S1b (Positioning on Adaptation)
est une posture déclarative sans substance opérationnelle.*

### 2.3 Rupture de la contrainte descendante (axe vertical N → N-1)

Chaque niveau encadre les niveaux adjacents. Une défaillance ou un excès à N désencadre
ou surcontraint N-1.

**Déficit** : le niveau inférieur opère sans cap — il improvise, se fragmente, se perd dans
l'exécution locale.

**Excès** : le niveau inférieur est hyperspécifié, ses acteurs perdent leur capacité
d'adaptation et d'initiative.

*Exemple : S2a (Delegated Governance) excessif → O2a est bureaucratisé à l'excès,
et I2a est atomisé en silos.*

### 2.4 Dette organisationnelle (impact cumulatif)

Les désalignements persistants entre S, O et I produisent des dysfonctionnements chroniques
dont la cause racine est structurelle, invisible en diagnostic ponctuel.
**C'est le risque le plus utile pour la justification d'une mission d'audit** : il permet
de passer du constat symptomatique à l'argument systémique.

*Exemple : S1b positionné sur la transformation mais O1b inexistant et I1b non développé
→ l'organisation déclare innover, mais ne produit aucune transformation réelle.
La dette s'accumule, les projets s'enchaînent sans capitalisation.*

### 2.5 Décrochage isomorphique (cohérence de colonne)

Les trois capacités partageant le même `axis + pole` (ex. I1a / O1a / S1a) forment une
"colonne isomorphique". Une capacité peut être formellement active à un niveau mais
déconnectée de ses homologues verticaux : il y a présence sans traduction.

*Exemple : I2b bien développé (acteurs collaboratifs) mais O2b absent (aucun dispositif
de structuration de la coopération) → la coopération individuelle reste informelle,
fragile, non institutionnalisée.*

### 2.6 Inadéquation de régime (spécifique aux contextes de transformation)

R6 est utilisé dans des missions de transformation. Un risque propre à ce contexte :
une capacité calibrée pour un régime stable devient un facteur de rigidité dans un régime
de transition, et inversement.

**Déficit en régime de transformation** : la capacité stabilisatrice (pôle a) bloque
l'adaptation au lieu de l'ancrer.

**Excès en régime de transformation** : la capacité transformatrice (pôle b) accélère
au-delà de la capacité d'absorption de l'organisation.

---

## 3. Trois approches d'amélioration

### Approche A — Seeds structurels dans le prompt (comme generate_questions)

**Principe** : Ajouter une section `STRUCTURAL RISK SEEDS` dans `generate_fiche_risque.txt`,
analogue aux `THEMATIC SEEDS` de `generate_questions.txt`. Pour chaque bullet de
`risk_insufficient` et `risk_excessive`, le LLM doit couvrir un seed structurel précis.

**Prompt section à ajouter** :
```
=== STRUCTURAL RISK SEEDS ===
Each of the 5 bullets must be grounded in one of the following R6 structural mechanisms,
in this exact order:
1. Polar imbalance: what happens to the twin pole on the same axis when this capacity
   is absent / overactivated
2. Emergence blockage / overflow: how a deficit / excess at this level prevents
   or saturates the capacity at the level above
3. Constraint rupture / over-constraint: how a deficit / excess at this level
   disorients or over-specifies the level below
4. Organizational debt: what cumulative systemic dysfunction is produced over time
5. Isomorphic disconnection: how a gap between this capacity and its vertical
   homologues creates invisible structural misalignment
```

**Avantages** : Simple à implémenter (prompt uniquement), aucun changement de code,
compatible avec l'architecture actuelle, cohérent avec le pattern déjà utilisé.

**Limites** : Les seeds sont génériques. Le LLM ne sait pas que le pôle jumeau de I1a
est I1b ("Demonstrating Innovation"), ni que I1a active O1a. Les risques restent
structurellement typés mais pas topologiquement ancrés.

---

### Approche B — Injection du contexte relationnel de la capacité

**Principe** : Injecter dans le prompt les noms et IDs des capacités relationnellement
liées, lus depuis `axioms.yml`. Le LLM génère des risques nominativement ancrés dans
la topologie réelle.

**Données disponibles dans `axioms.yml`** pour chaque capacité :
- `enables` → capacité N+1 activée (ex. I1a → O1a)
- `emerges_from` → capacité N-1 source (ex. O1a → I1a)
- pôle jumeau : même `axis`, `pole` opposé (dérivable par code)

**Injection dans le prompt** :
```
=== RELATIONAL POSITION OF {capacity_id} ===
Twin pole (same axis, opposite pole): {twin_id} — {twin_name}
  → Polar tension: if {capacity_id} is absent/excessive, {twin_name} is deprived
    of its regulatory counterweight.
Enables (level above): {enables_id} — {enables_name}
  → Emergence: {capacity_id} is the foundation of {enables_name}.
    A deficit blocks its constitution; an excess saturates it.
Emerges from (level below): {emerges_from_id} — {emerges_from_name}  [if exists]
  → Constraint: {capacity_id} encadres {emerges_from_name}.
    A deficit leaves it without direction; an excess over-constrains it.
```

**Avantages** : Risques nominativement ancrés, diagnostics traçables vers les capacités
adjacentes, directement utilisables dans un rapport d'audit pour relier les constats.

**Limites** : Nécessite un enrichissement de la fonction `generate_fiche_risque()` dans
`ai_generate.py` pour calculer et injecter `twin_id`, `twin_name`, `enables_id`,
`enables_name`, etc. Modification de code modérée (pas de changement de schéma DB).

---

### Approche C — Risques typés comme champs séparés (refonte du modèle de données)

**Principe** : Remplacer les deux champs génériques `risk_insufficient` / `risk_excessive`
par 4 à 6 champs correspondant aux catégories structurelles. Chaque champ est une
phrase-diagnostic ciblée.

**Schéma proposé** :
```
risk_polar_imbalance     : 1-2 phrases — déséquilibre sur l'axe horizontal
risk_emergence_blockage  : 1-2 phrases — blocage / saturation du niveau N+1
risk_constraint_rupture  : 1-2 phrases — désencadrement / surcontrainte du niveau N-1
risk_organizational_debt : 1-2 phrases — dysfonction systémique cumulée
```

`risk_insufficient` et `risk_excessive` deviendraient des propriétés émergentes de
ces 4 champs (ou pourraient être supprimés).

**Avantages** : Taxonomie des risques explicite et stable, utilisable directement dans
les exports DOCX comme sections de rapport structurées, force le LLM à traiter chaque
mécanisme séparément (moins de dérive généraliste).

**Limites** : Changement de schéma DB (migration), changement de l'UI (onglet Fiche),
changement de l'export DOCX. Coût le plus élevé des trois approches.

---

## 4. Recommandation

| Approche | Coût | Gain qualitatif | Cohérence avec l'architecture |
|----------|------|-----------------|-------------------------------|
| A — Seeds structurels | Faible (prompt seul) | Moyen | Fort |
| B — Injection relationnelle | Moyen (ai_generate.py) | Élevé | Fort |
| C — Champs typés | Élevé (schéma + UI + DOCX) | Très élevé | Rupture partielle |

**Recommandation immédiate** : Approche A + B combinées.

- A est implémentable aujourd'hui sans risque : elle force la structure dans le prompt.
- B l'ancre dans la topologie réelle sans changer le schéma DB.
- C est une évolution souhaitable à moyen terme si R6 évolue vers des rapports d'audit
  structurés par type de risque — à considérer quand la taxinomie sera stabilisée en usage.

La combinaison A+B ne modifie que `generate_fiche_risque.txt` et `generate_fiche_risque()`
dans `ai_generate.py`. Aucun changement de schéma, aucune migration, aucune modification UI.
