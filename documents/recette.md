# Rapport de recette

**Étudiant :** Abdoul Ahad Mbacké DIOUF. **Dernier contrôle S2 :** 26/11/2026. **Relecture du code S2 :** parcours et vues contrôlés ; relecture finale à confirmer par l’étudiant.
**Commit applicatif :** S2 `65d92c4` et `4b24b67`. **Images API/web :** construites localement pour S3 ; digests non encore relevés.
**Contexte de déploiement et commit de configuration :** à renseigner.

## 1. Conditions d’exécution

Les contrôles S2 ont été exécutés sur le serveur personnel, avec Python 3.12 et PostgreSQL 17. Les tests d'intégration utilisent exclusivement `campus_test` ; ils refusent de travailler sur une autre base. Chaque test crée un jeu au nom unique et supprime uniquement ce jeu à la fin. Les fichiers CSV sont ceux du dossier `data/`. Aucun mot de passe ni DSN complet n'est conservé dans ce rapport.

## 2. Résultats par exigence

| ID du référentiel | **Préconditions** | Action / commande | Attendu | Observé | Preuve | Résultat |
|---|---|---|---|---|---|---|
| US01–US02 | `campus_test`, tables créées | `python -m pytest -q` | Créer/lister/ouvrir ; 409/404 | Création et compteurs contrôlés ; refus observés dans les tests | `proofs/s2-api-tests.txt` et `api/tests/test_api_flow.py` | Validé au niveau API |
| US03 | Jeu avec dépôts et mesures | Test de suppression | 204 sans corps ; cascade | 204, puis 0 dépôt et 0 mesure liés | `proofs/s2-api-tests.txt` | Validé au niveau API et de la confirmation UI |
| US04–US07 | Trois CSV fournis | Dépôt HTTP puis worker | 202/pending, résultats 63/0/0, 4/7/1, échec en-tête, redépôt 0/0/63 | Comptages et statuts confirmés par 15 tests réussis | `proofs/s2-api-tests.txt` | Validé au niveau API/worker |
| US08–US09 | Jeu avec mesures et dépôt failed | Statistiques, filtres et relance | Indicateurs et transitions conformes | Somme 63, période inversée 422, relance failed 202, succeeded 409 | `proofs/s2-api-tests.txt` | Validé au niveau API et de l’UI de démonstration |
| US10 | Pile Compose S3, jeu témoin 63 mesures | `down` sans `-v`, recréation, relecture par UUID | Même jeu et 63 mesures | UUID du jeu et du dépôt inchangés ; 63 mesures relues | `proofs/s3-persistance.txt` | Validé en S3 sur ce serveur |

Résultats autorisés : validé, échoué, **non exécuté**, **non applicable avec justification**.
Ne jamais remplacer une observation par le **résultat attendu**. Si une commande
n’a pas été lancée, indiquer non exécuté même si sa syntaxe paraît correcte.

## 3. Exemple de rédaction d’un cas

**Exemple méthodologique à exécuter, pas résultat déjà obtenu :**

- **Précondition :** jeu de données créé, fichier `data/mesures-salles-2026-10-05.csv` déjà ingéré (63 mesures).
- **Action :** déposer le même fichier une seconde fois, puis lancer le worker.
- **Attendu :** dépôt `succeeded` avec 0 acceptée et 63 doublons ; `measurement_count` **toujours égal à 63 à la relecture**.
- **Observé :** à compléter après exécution.
- **Preuve :** requête, réponse et lecture suivante dans le même environnement.
- **Conclusion :** à compléter ; une assertion sur le seul statut `succeeded` est insuffisante.

## 4. Expériences de déploiement et de reprise

Pour chaque expérience, conserver identifiants et données avant/après :

- **Persistance** Compose : UUID témoin et **volume** conservé après recréation.
- **Réconciliation** API : Pod précédent/remplaçant et états prêts observés.
- **Panne DB :** liveness, readiness, requêtes métier et reprise.
- **Cloud :** version, contexte VM et références d’images cohérents.
- **Rollback :** ancienne release API et web effectivement retrouvée.
- **Restauration :** base cible distincte, UUID/contenu retrouvé et durée mesurée.

Indiquer les erreurs transitoires et les limites de chaque expérience.
Un tableau de résultats n’oblige pas à conclure que tout a fonctionné.

## 5. Anomalies connues

| ID | Reproduction minimale | Attendu/observé | Impact | Priorité | Correction ou contournement | État |
|---|---|---|---|---|---|---|
| À renseigner | Données et étapes | Écart précis | Utilisateur/technique | Justification | Action | Ouvert/clos |

Une correction est clôturée après un nouveau contrôle du scénario affecté.
Relier le résultat à son **commit** pour éviter d’attribuer une ancienne preuve
à une version plus récente non testée.

## 6. Synthèse de remise

Lister critères validés, écarts restants, opérations non exécutées et limites.
Indiquer où trouver les preuves expurgées et quelle version le jury doit évaluer.

## Comment annoter une preuve

Donnez un nom explicite à chaque sortie conservée : séance, scénario et version.
Convention commune du support : `proofs/sN-sujet.ext`, par exemple
`proofs/s3-persistance.txt`, `proofs/s4-reconciliation.txt`,
`proofs/s6-overlay-s5.yaml` ou `proofs/latence-k3d.json`. Les fichiers privés
(dump, sorties non expurgées) vont uniquement dans `proofs/private/`, ignoré par Git.
Ajoutez une phrase qui indique ce que le lecteur doit observer. Exemple de forme :
« Sur la réponse de relecture, comparer l’identifiant du jeu, son nombre de mesures et sa somme de contrôle à ceux relevés avant
la recréation. » Complétez ensuite avec vos valeurs et votre **résultat réel**.

N’utilisez pas un exemple du cours comme **résultat observé**. Expurgez les secrets,
mais conservez les statuts, identifiants de jeux de données fictifs et messages utiles
pour comprendre le scénario.

## Contrôle navigateur S2 — 26/11/2026

Chromium a chargé l'interface depuis Nginx sur le serveur de développement. J'ai observé la création d'un jeu, un dépôt `pending`, puis un rapport de 63 acceptées après `worker --once` ; le compteur du jeu sélectionné et les trois salles ont été vérifiés. Le fichier mixte a affiché 4 acceptées, 7 raisons de rejet et 1 doublon. L'en-tête invalide a affiché l'échec et permis la relance. L'annulation de suppression n'a pas supprimé le jeu ; une suppression confirmée a laissé la liste vide. Le focus clavier, le message d'erreur réseau, l'affichage littéral d'un nom contenant `<b>` et l'absence de débordement horizontal à 390 px ont été observés. Les captures se trouvent dans `proofs/s2-interface-*.png` ; détails dans `proofs/s2-api-tests.txt`.

Ces observations concernent S2 sur le serveur personnel. Elles ne valident ni la persistance après redémarrage, ni Compose complet, Kubernetes ou AWS.

## Extension des vues S2 — 26/11/2026

La maquette PDF a été comparée au rendu. Les vues Dépôts, Rapport, Indicateurs et gestion des jeux sont navigables. Le dépôt direct crée un jeu puis enregistre le CSV ; l’historique global permet de rouvrir le rapport après actualisation. La suppression d’un dépôt `succeeded` ou `failed` retire ses mesures et conserve le jeu ; un dépôt `pending` renvoie 409. La vérification sur `campus_test` donne 15 tests réussis. Les parcours Chromium ont contrôlé dépôt direct, traitement 63 mesures, rapport, indicateurs, historique après rechargement, annulation puis confirmation de suppression et affichage mobile à 390 px, sans erreur JavaScript. Voir `proofs/s2-interface-vues.txt`.

Écart restant : les erreurs de ligne exposées par l’API comprennent `line` et `reason`, pas `room`, `field` ni `value`. Le tableau d’erreurs de la maquette est donc simplifié.

## Contrôles Compose S3 — 26/11/2026

Quatre services actifs : DB et API healthy, worker et web Up. Les processus API et worker exécutent avec UID 10001. `/health/live`, `/health/ready`, `/api/version`, `/api/datasets`, `/app.js` et `/styles.css` ont répondu 200 via Nginx. Un dépôt CSV du témoin a produit 63 mesures ; après `down` sans `-v` puis recréation, les mêmes UUID et 63 mesures ont été relus. Pendant `stop db`, live est resté 200, ready et la liste ont répondu 503 ; après `start db`, ready a retrouvé 200 et le témoin 63 mesures. Voir `proofs/s3-stack.txt`, `proofs/s3-worker.txt`, `proofs/s3-persistance.txt` et `proofs/s3-panne-db.txt`.
