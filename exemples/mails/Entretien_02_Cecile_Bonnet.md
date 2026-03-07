# Entretien Diagnostic R6 — Système de Gestion des E-mails Commerciaux

**Date :** 16 novembre 2024  
**Interviewée :** Cécile Bonnet, Responsable Système d'Information (12 ans d'ancienneté)  
**Consultant R6 :** Expert Diagnosticien  
**Durée :** ~15 minutes  

---

**Consultant :** Cécile, je voudrais comprendre comment vous avez approché le projet de système automatisé pour les e-mails commerciaux. Racontez-moi concrètement comment ce projet s'est déroulé. D'abord, qui vous a demandé quoi, exactement ?

**Responsable SI :** Donc, il y a environ neuf mois, le directeur commercial est venu nous voir — moi et mon équipe IT — avec une demande assez claire : « On veut automatiser les premières réponses aux mails commerciaux pour que nos commerciaux fassent moins d'administratif et plus de vente ». C'était présenté comme une question de productivité.

**Consultant :** Et qu'avez-vous fait ?

**Responsable SI :** On a commencé par une phase de spécification. On s'est assis avec le directeur commercial et avec deux ou trois commerciaux pour comprendre quels types de mails arrivaient, quels types de réponses on devrait automatiser. On a identifié les mails « simples » — des demandes de brochure, des demandes de prise de rendez-vous, des accusés de réception de devis.

**Consultant :** Comment avez-vous identifié ces mails « simples » ?

**Responsable SI :** On a fait une analyse sur trois semaines. On a regardé l'historique des mails, on a catégorisé. Et puis on a parlé aux commerciaux : « Est-ce que ces demandes-là, vous pourriez y répondre avec une réponse standard ? » Beaucoup ont dit oui. Donc on s'est dit que c'était faisable.

*[Investigation Niveau O — Conception du processus]*

**Consultant :** Et les mails qui n'étaient pas « simples » ?

**Responsable SI :** Là, on s'est dit qu'il faudrait que le système soit assez intelligent pour reconnaître les mails compliqués et les laisser de côté. Mais en vrai, c'était très difficile. On a essayé d'utiliser des règles — des mots-clés, des patterns — pour les détecter. Mais il y en avait toujours qui passaient à travers. Un mail où le client pose deux questions en même temps, par exemple — c'est technique à détecter.

**Consultant :** Donc vous avez mis en place des règles, mais elles ne capturaient pas tous les cas particuliers ?

**Responsable SI :** Exactement. Et à un moment, on s'est dit : « On va faire un prototype, on va le tester en live pendant deux, trois semaines, et on verra quels sont les soucis qui remontent ». C'est ce qu'on a fait.

**Consultant :** Comment s'est déroulée cette phase de test ?

**Responsable SI :** Alors, là, c'est intéressant. On a déployé le système avec une notification : quand une réponse automatique était envoyée à un client, le commercial responsable de ce compte recevait une copie. L'idée, c'était qu'il puisse contrôler et ajuster si besoin. Ça a marché — genre, on a eu du feedback sur certains e-mails où le système ne s'était pas bien exprimé, ou où il y avait une incohérence de ton.

**Consultant :** Comment le commercial signalait-il un problème ?

**Responsable SI :** On avait une procédure : il y avait un bouton « signaler un problème » qui ouvrait un ticket IT. C'était simple, vraiment. On a reçu, je ne sais pas, une trentaine de signalements pendant les trois semaines de test.

**Consultant :** Et vous avez fait quoi avec ces signalements ?

**Responsable SI :** On en a analysé la moitié. Il y en avait vraiment des utiles — des cas où le système s'était trompé — et d'autres où le commercial n'était pas d'accord sur le ton ou sur la proposition. On a affiné les règles, on a modifié un peu le texte des templates. Et puis... on a déployé en production.

*[Investigation Niveau O — Fermeture de la boucle de feedback]*

**Consultant :** Vous dites « et puis on a déployé ». Qu'est-ce qui s'est passé après le déploiement en production ?

**Responsable SI :** Là, honnêtement, ça s'est compliqué. On a retiré le système de notification des copies d'e-mail automatiques — c'était une décision consciente, on trouvait que c'était trop verbeux pour le commercial, trop de mails. On s'est dit « ils vont voir les tickets qui arrivent pour les problèmes vraiment importants ».

**Consultant :** Donc vous avez fermé la boucle de feedback ?

**Responsable SI :** Oui, en quelque sorte. Les commerciaux ne reçoivent plus les copies systématiques. Si un client se plaint ou si quelque chose va mal, ils le découvrent directement — soit le client les appelle, soit ils voient qu'on ne leur a pas bien relancé.

**Consultant :** Vous avez reçu combien de tickets après le déploiement ?

**Responsable SI :** Beaucoup moins qu'on ne l'aurait pensé. Peut-être quatre ou cinq par semaine, parfois zéro. Honnêtement, on s'est dit « c'est bon, le système fonctionne ». Mais en parlant à un directeur commercial récemment, j'ai compris qu'il y avait des problèmes que les commerciaux ne signalaient pas.

*[Investigation Niveau O — Perte de visibilité opérationnelle]*

**Consultant :** Quel type de problèmes ?

**Responsable SI :** Des trucs comme : le système a promis une relance dans 48 heures, mais qui est responsable de cette relance ? Ou : le mail automatique dit « on étudiera votre demande », mais qu'est-ce que ça signifie réellement ? On avait réfléchi à ça pendant la conception, mais après le déploiement, on s'est dit « les commerciaux vont gérer les exceptions, point barre ».

**Consultant :** Vous aviez pensé à la gestion des exceptions, mais vous aviez des hypothèses sur qui les gérerait ?

**Responsable SI :** Oui, j'imagine. Je veux dire, pour nous, c'était clair — le système fait son boulot de base, et les exceptions, c'est aux commerciaux de les rattraper. Mais en vrai, on n'a jamais formalisé ça, on n'a jamais dit : « Voici ce qui se passe si... Voici votre responsabilité ».

*[Investigation Niveau O — Absence de définition de rôles]*

**Consultant :** Pourquoi cette absence de formalisation ? C'était un choix délibéré ou c'est simplement arrivé ?

**Responsable SI :** Honnêtement, c'est un peu des deux. On était sous timeline serrée pour déployer. La direction commerciale voulait le système opérationnel avant la fin du trimestre pour montrer les bénéfices. Du coup, on a priorisé l'implémentation technique sur les processus de gestion après déploiement. C'est une mauvaise pratique, je le sais, mais c'est ce qui s'est passé.

**Consultant :** La direction commerciale avait un objectif de timing ?

**Responsable SI :** Oui, montrer que la charge administrative était réduite, que les commerciaux pouvaient se concentrer sur la prospection et le conseil. C'était l'objectif du projet.

*[Investigation Niveau S — Pression de résultats]*

**Consultant :** Et depuis le déploiement, vous avez mesuré si cet objectif était atteint ?

**Responsable SI :** Pas vraiment. On a déployé, on s'est dit « ok, c'est fait ». On a eu quelques retours informels de commerciaux qui disaient « oui, ça aide un peu », mais on n'a pas fait une véritable évaluation post-implémentation. Je sais que c'est un écueil classique, mais on ne l'a pas fait.

**Consultant :** Avez-vous observé une réduction du volume de mails traités par les commerciaux ?

**Responsable SI :** C'est une bonne question. Non, pas vraiment. Ce qui est étrange, c'est que le nombre de mails entrants semble avoir augmenté. Je pense que c'est un phénomène externe — plus de clients qui nous contactent par e-mail peut-être — mais du coup, même si le système automatise, le volume global est plus important, donc les commerciaux travaillent plus, pas moins.

**Consultant :** Et les mails qu'ils doivent vérifier ou corriger — ceux où le système ne s'en est pas bien chargé — vous avez une idée de la proportion ?

**Responsable SI :** Non. C'est ça, justement. Depuis qu'on a retiré le système de notification, on n'a plus de visibilité. Je suppose que certains commerciaux font la vérification, d'autres pas. Mais on ne le savons pas.

**Consultant :** Vous n'avez pas de logs, pas de métriques qui vous diraient combien de mails automatisés génèrent une action manuelle après ?

**Responsable SI :** Pas vraiment. On a des logs techniques du système — combien de mails entrants, combien classés comme simples et automatisés, combien rejetés — mais rien qui dise « ce mail automatisé a ensuite été modifié ou corrigé par un humain ». C'est une vraie faille.

*[Investigation Niveau O — Absence de métriques de suivi]*

**Consultant :** C'est une faille techniquement, ou organisationnellement ?

**Responsable SI :** Les deux, probablement. Techniquement, on aurait pu ajouter des flags ou des logs. Mais organisationnellement, on n'avait pas défini qui avait besoin de ces informations et pour quel objectif. On s'est dit « le système fonctionne », c'est tout.

**Consultant :** Si vous pouviez revenir en arrière, qu'auriez-vous changé ?

**Responsable SI :** Au minimum, une vraie clause post-déploiement. Genre : deux semaines après le lancement, on fait un point avec les utilisateurs, on collecte du feedback, on identifie les gaps, on corrige. Et parallèlement, on mettrait des métriques en place pour savoir si l'objectif global — libérer du temps — est réellement atteint. Parce que là, on a l'impression que c'est un succès technique mais qu'on ne sait pas si c'est un succès opérationnel.

**Consultant :** Merci, Cécile. C'est très clair.

---

## Synthèse des observations

**Niveau I (Individuel)** : Cécile et l'équipe IT ont conçu et implémenté le système selon une approche méthodique, mais ont retiré les mécanismes de visibilité post-déploiement (notifications aux utilisateurs, collection systématique de feedback).

**Niveau O (Organisationnel)** : Le processus de support post-implémentation est absent. Il n'y a pas de boucle de feedback formalisée, pas de définition claire des rôles de vérification/correction, pas de métriques de suivi. Le système opère en isolement — les exceptions sont capturées ponctuellement (tickets IT) mais pas analysées systématiquement pour améliorer le système ou redéfinir les processus.

**Niveau S (Stratégique)** : La direction a imposé un délai serré pour montrer des résultats rapides. Cette pression a conduit l'IT à prioriser la mise en place technique sur la conception organisationnelle et le suivi. L'absence d'évaluation post-implémentation reflète aussi une vision du projet comme « implémentation technique » plutôt que comme « transformation du travail commercial ».

**Désalignement** : L'absence de structure O (suivi, feedback, métriques) reflète une logique S déformée (résultats immédiats avant robustesse) que les individus (I) ne peuvent pas compenser car ils n'ont pas d'outils ni de visibilité.
