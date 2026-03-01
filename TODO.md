# TODO

Supprimer le "observable" de "capacity_translation" et du premier onglet "fiche".
Travailler par étapes de génération :
- générer
- valider

On va décomposer les étapes de génération pour construire la base de manière plus itérative.
- J'ai créé de nouveaux prompts par duplication des anciens.
- Il faut enlever ce qui est inutile dans les prompts existants.
- Il faut créer les traitements sur la base de cest prompts.
- Il faut mettre à jour les scripts de cli si nécessaire.

Nouvelles étapes du traitement
  - générer l'information générale : `capacity_translation.label` `capacity_translation.definition` `capacity_translation.central_function` (prompt : generate_fiche.txt)
  - générer les risques pour l'organisation `capacity_translation.risk_insufficient` `capacity_translation.risk_excessive` (prompt : generate_fiche_risques.txt)
  - générer les `questions_translations` et les observables `observable_item_translation` (prompt : generate_questions.txt)
  - générer les items (prompt : generate_questions_items.txt)
  - générer les coaching :  `coaching_translation` (prompt : generate_coaching.txt)
