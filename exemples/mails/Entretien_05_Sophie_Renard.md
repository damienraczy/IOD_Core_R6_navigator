# Entretien Diagnostic R6 — Système de Gestion des E-mails Commerciaux

**Date :** 20 novembre 2024  
**Interviewée :** Sophie Renard, Responsable Assurance Qualité Client (7 ans d'ancienneté)  
**Consultant R6 :** Expert Diagnosticien  
**Durée :** ~15 minutes  

---

**Consultant :** Sophie, je comprends que vous pilotez la satisfaction client et que vous avez une visibilité sur ce qui se passe avec les clients, notamment les insatisfactions. Racontez-moi une situation concrète que vous avez observée depuis le lancement du système d'e-mail automatique.

**Responsable QA :** Bien sûr. Alors, depuis six mois, on observe une augmentation des plaintes de clients qui concernent une catégorie spécifique : « on m'a promis une relance, et personne ne m'a rappelé ». C'est devenu assez récurrent, disons deux à trois cas par semaine.

**Consultant :** Pouvez-vous me donner un exemple concret ?

**Responsable QA :** Oui. Un client nous envoie un e-mail : « Je cherche une solution pour [besoin spécifique] ». Le système envoie une réponse automatique : « Nous avons bien reçu votre demande et nous vous recontacterons dans les 48 heures ». Sauf que 48 heures passent, 72 heures passent, et le client n'a pas entendu parler de nous. Il nous rappelle, il dit « j'ai été oublié », ou pire, il part voir un concurrent.

**Consultant :** Vous avez des chiffres sur ça ? Combien de clients partiront, ou arrêtent de nous parler ?

**Responsable QA :** Pas précis, mais j'ai noté six cas le mois dernier où un client disait explicitement « on m'a dit 48 heures, ça fait trois jours ». Dans trois de ces cas, on les a perdus — ils ont signé avec un concurrent. Dans les trois autres, on a pu rattraper, avec des excuses et une relance personnalisée.

*[Investigation Niveau O — Rupture du contrat de service]*

**Consultant :** Vous avez creusé pour savoir pourquoi « 48 heures » n'était pas respecté ?

**Responsable QA :** Oui. Je me suis assis avec trois ou quatre commerciaux pour comprendre la chaîne. Et le truc, c'est qu'il n'y a pas de chaîne clair. Le mail arrive, le système dit « on va vous recontacter dans 48 heures ». Mais qui ? Le commercial assigné à ce prospect ? Le commercial qui regarde juste l'e-mail quand il a le temps ? Quelqu'un d'une équipe d'admission ?

**Consultant :** Et le commercial, il savait qu'il avait une obligation de relance en 48 heures ?

**Responsable QA :** Ah, ça, c'est intéressant. Quand j'ai posé la question, la plupart ont dit « non, on ne m'a pas dit ça ». Ou « j'ai lu que le système promettait 48 heures, mais je n'ai jamais signé un accord pour faire une relance en 48 heures ». C'est pas ma job, disaient-ils.

*[Investigation Niveau O — Rupture de responsabilité]*

**Consultant :** Vous pensez que le système qui envoie une promesse de 48 heures, c'était la bonne chose ?

**Responsable QA :** Non. Pas sans avoir d'abord défini qui était responsable de la relance et comment ça se passerait. Le système promet 48 heures, mais le commercial ne sait pas que c'est sa responsabilité. C'est un contrat non signé avec le client.

**Consultant :** Avez-vous communiqué ça à quelqu'un — l'IT, le directeur commercial ?

**Responsable QA :** Oui, j'ai signalé le problème à Frédéric, le directeur commercial. Je lui ai envoyé un e-mail en lui montrant ces cas où on avait perdu des clients parce qu'on n'avait pas tenu la promesse. Et je lui ai proposé deux solutions : soit on enlève la promesse de « 48 heures » du mail automatique, soit on crée un vrai processus pour assurer que la relance se fait.

**Consultant :** Qu'a-t-il répondu ?

**Responsable QA :** Euh, il ne m'a pas répondu. J'ai relancé une fois, toujours rien. Donc j'en ai conclu que ce n'était pas une priorité pour lui. Et maintenant, le problème persiste.

*[Investigation Niveau S — Non-réception d'un signal d'alerte]*

**Consultant :** Vous continuez à recevoir des plaintes ?

**Responsable QA :** Oui. Tous les mois. Et honnêtement, c'est un problème de réputation. Les clients pensent qu'on est une boîte désorganisée. Et c'est pas faux, à ce stade.

**Consultant :** Pensez-vous que ce problème existe aussi pour les autres promesses que le système envoie ?

**Responsable QA :** Oui, certainement. Par exemple, le système dit « nous vous enverrons une documentation complète ». Mais c'est qui qui envoie ? C'est pas défini. Ou « un commercial va vous appeler pour discuter de vos besoins ». Quand ? Vendredi ? La semaine prochaine ? Quand exactement ?

*[Investigation Niveau O — Généralisation du problème]*

**Consultant :** Vous avez documenté ça ? Vous aviez une liste des promesses que le système fait et le statut de chaque promesse ?

**Responsable QA :** J'ai esquissé quelque chose dans un document, mais c'est pas formalisé. Je l'ai partagé avec Frédéric aussi. Pas de réponse.

**Consultant :** Avez-vous essayé d'aborder le sujet différemment ?

**Responsable QA :** J'ai parlé à Laurent Mercier — un commercial senior — et je lui ai demandé comment il gérait les promesses du système. Il m'a dit qu'il avait créé un tableau personnalisé pour tracker les délais promis et assurer la relance. Donc lui, il a trouvé une solution personnelle.

**Consultant :** Et c'est efficace, sa solution ?

**Responsable QA :** Oui, à titre individuel. Mais c'est un workaround. C'est pas une solution systémique. Et ça lui prend du temps — du temps que, supposément, le système devait libérer.

*[Investigation Niveau I — Compensation individuelle vs. absence de processus]*

**Consultant :** Vous pensez que le système était mal conçu dès le départ ?

**Responsable QA :** Pas mal conçu techniquement. Techniquement, il génère des réponses, c'est super. Mais il n'y avait pas de réflexion sur ce que ça signifiait de faire une promesse à un client. Ou plus généralement, il n'y avait pas de processus définissant : « Quand le client reçoit cette réponse, qu'est-ce qui se passe après ? »

**Consultant :** Si vous aviez pu intervenir avant le lancement, qu'auriez-vous demandé ?

**Responsable QA :** D'abord, une liste claire de toutes les promesses dans les mails automatiques. Ensuite, pour chaque promesse, définir qui est responsable, quand c'est fait, comment on le suivi. Et puis, une réflexion simple : « Est-ce que cette promesse est réaliste ? Est-ce qu'on peut la tenir ? »

**Consultant :** Vous pensez que certaines promesses du système ne sont pas réalistes ?

**Responsable QA :** Oui. « Nous vous recontacterons dans les 48 heures » — c'est pas réaliste si le commercial est en congé ou débordé. « Nous vous fournirons une documentation complète » — c'est vague, c'est quoi, « complète » ? Une présentation PowerPoint ? Un PDF ? Une réunion ?

*[Investigation Niveau O — Imprécision des engagements]*

**Consultant :** Cela vous impacte comment, concrètement ? Qu'est-ce que vous faites, vous ?

**Responsable QA :** Je dois gérer les insatisfactions. Ça signifie : appels clients, e-mails d'excuse, essai de rattrapage. Et puis je dois documenté les écarts, essayer d'identifier des patterns. C'est du travail supplémentaire, parce que le système crée des attentes qu'on ne tient pas.

**Consultant :** Vous trouvez que c'est une charge qui s'ajoute à votre travail ?

**Responsable QA :** Oui, absolument. Avant, les commerciaux répondaient directement, donc il y avait une cohérence — la personne qui répondait était aussi celle qui assurait la suite. Maintenant, c'est fragmenté. Le système promet quelque chose, le commercial ne sait pas que c'est sa responsabilité, je dois corriger.

*[Investigation Niveau I — Accumulation de charge à un tiers]*

**Consultant :** Vous pensez que c'est un phénomène général dans l'entreprise, ou limité au domaine client ?

**Responsable QA :** Je pense que c'est limité au domaine client pour l'instant. Mais globalement, c'est un exemple de ce qui se passe quand on déploie une solution sans refléchir aux processus alentour.

**Consultant :** Merci, Sophie. Très utile.

---

## Synthèse des observations

**Niveau I (Individuel)** : Sophie observe et documente les défaillances du système (mails de relance non envoyés, promesses non tenues). Elle tenté de communiquer le problème au management, sans réponse. Elle compense en gérant les insatisfactions clients après coup. Parallèlement, Laurent Mercier met en place un système personnel de tracking pour assurer que les promesses du système sont tenues.

**Niveau O (Organisationnel)** : Le processus post-mail automatique est absent. Les mails génèrent des promesses (« 48 heures », « documentation complète », etc.) sans que personne n'ait formellement défini qui est responsable de les tenir, comment, et quand. Il n'existe pas de liste canonique des promesses ni de leur statut de faisabilité. Le système opère isolé de la chaîne commerciale complète (promesse → assignation → exécution → suivi).

**Niveau S (Stratégique)** : La direction commercial a déployé le système sans inclure de réflexion stratégique sur l'impact sur la promesse client. Le signal d'alerte de Sophie (perte de clients, dégradation de réputation) a été ignoré ou non reçu. Il n'existe pas de gouvernance post-déploiement pour ajuster la stratégie en fonction de la réalité observée.

**Désalignement** : S (déploiement rapide pour des résultats visibles) a imposé l'absence de O (définition des responsabilités et des processus de suivi des promesses), ce qui crée une charge en I (Sophie gère les crises; Laurent crée un système personnel). Les individus compensent une absence structurelle qui ne peut pas être résolue à leur niveau.
