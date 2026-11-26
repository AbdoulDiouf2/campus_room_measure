# Journal de projet — CampusData

**Étudiant :** Abdoul Ahad Mbacké DIOUF. **Dépôt :** CampusData (`aivancity-dev`).

Je note ici le travail réalisé, les problèmes rencontrés et les résultats que j'ai effectivement observés. Je ne consigne aucun secret.

## 1. Travail réalisé

| Séance/étape | Mon travail et mes observations | Référence | Difficulté | Prochaine action |
|---|---|---|---|---|
| S1 — 26/11/2026 | J'ai pris connaissance de l'énoncé et relu le dossier de conception rédigé avec l'aide de l'IA. J'ai activé le venv : Python 3.12.3. J'ai démarré PostgreSQL, affiché `healthy`, puis l'API. `/health/live` et `/api/version` ont répondu `200`. Après correction du mot de passe PostgreSQL, `/health/ready` est passé de `503` à `200`. J'ai ensuite obtenu `2 passed, 1 warning` avec pytest, puis `{"version":"dev"}` via le proxy web sur le port 8080. | `documents/architecture.md` ; `proofs/s1-preparation.txt`, déjà renseigné avec ces observations. | La DB acceptait une connexion interne, mais refusait l'API depuis le poste. | Commencer S2 et revérifier l’adresse de la passerelle si le réseau Docker change. |
| S2 — 26/11/2026 | Les modèles, schémas, services, routes, worker, interface et tests S2 ont été réalisés. J'ai relu le code produit. Les contrôles exécutés donnent 14 tests réussis, Ruff sans erreur, syntaxe JS valide et réponse HTTP 200 via Nginx pour la page et la liste des jeux. Deux services systemd utilisateur maintiennent désormais l'API et le worker après la fermeture de l'IDE ; le parcours de dépôt a réussi avec ces services. J'ai ouvert l'interface via Tailscale et confirmé que son style, sa version et la liste des jeux s'affichent. | `proofs/s2-api-tests.txt` ; `systemd/` ; `scripts/`. | Le statut `running` après arrêt brutal du worker reste un cas limite. | Confirmer les éventuelles bornes CSV supplémentaires du contrat, puis préparer S3. |
| S2 — reprise interface, 26/11/2026 | Après comparaison avec la maquette PDF, les vues Dépôts, Rapport, Indicateurs et gestion des jeux ont été séparées. Le dépôt direct, l’historique global, les cartes par salle et la suppression d’un dépôt terminé ont été ajoutés. J’ai revu les captures et les parcours Chromium ; 15 tests API passent. | `proofs/s2-interface-vues.txt` et captures `proofs/s2-interface-vues-*.png`. | Le rapport API ne fournit pas salle/champ/valeur pour chaque rejet ; seules ligne et raison sont disponibles. | Relire cette extension, puis commencer S3. |
| S3 — 26/11/2026 | J’ai construit les images API/web et démarré la pile Compose à quatre services. J’ai initialisé le schéma, puis observé les services sains, UID 10001 et les réponses HTTP 200. Le témoin S3 contient 63 mesures ; ses UUID et son compteur ont été retrouvés après recréation sans supprimer le volume. Lors d’un arrêt DB, live est resté 200, ready et la liste sont passés à 503, puis la reprise a été vérifiée. | `proofs/s3-stack.txt`, `proofs/s3-worker.txt`, `proofs/s3-persistance.txt`, `proofs/s3-panne-db.txt`. | Le `.env` ciblait d’abord `127.0.0.1` dans le conteneur ; je l’ai corrigé vers `db`. Les premières commandes de relecture utilisaient un `S3_DATASET_ID` vide, donc elles n’étaient pas probantes ; une relecture avec l’UUID explicite a validé la persistance. | Préparer S4. |

Je travaille seul sur ce dépôt ; il n'y a pas d'alternance de rôles à déclarer.

## 2. Raisonnement lors d’un blocage

- **Contexte et attendu :** je lance l'API sur mon serveur et j'attends `200` sur `/health/ready` pour vérifier sa connexion à la base PostgreSQL du Compose de développement.
- **Observation :** la DB était `healthy`, `/health/live` et `/api/version` répondaient `200`, mais `/health/ready` répondait `503` avec `Database unavailable`.
- **Diagnostic :** le mot de passe du rôle PostgreSQL ne correspondait pas au `.env` actuel. Un essai `psql` depuis le conteneur avait réussi ; l'essai avec un mot de passe volontairement faux a montré que ce test interne ne contrôlait pas l'authentification. Le test de connexion depuis le poste a révélé l'échec d'authentification.
- **Correction et résultat :** j'ai aligné le mot de passe du rôle avec `ALTER ROLE`, sans supprimer le volume. J'ai ensuite obtenu `200` et `{"status":"ready"}`.
- **Ce que j'ai appris :** `healthy` ne garantit pas que l'API possède les bons identifiants. Modifier `.env` ne modifie pas le mot de passe d'une base déjà initialisée. Le test doit utiliser le même chemin de connexion que l'API.
- **Second blocage, puis correction :** la requête via Nginx attendait trop longtemps. J'ai vérifié que le conteneur web utilisait le réseau `172.26.0.0/16`, que son nom d'hôte pointait vers la mauvaise passerelle et qu'UFW bloquait le port 8000. J'ai relancé Uvicorn sur `172.26.0.1`, autorisé uniquement ce trafic Docker dans UFW et adapté `extra_hosts` dans `compose.dev.yaml`. Le proxy a alors renvoyé `{"version":"dev"}`.
- **Contrôle des tests :** `python -m pytest -q` a donné `2 passed, 1 warning`. Ce sont les tests du socle, pas des tests métier.
- **Limite :** l'adresse `172.26.0.1` dépend du réseau Docker actuel. Je devrai vérifier la configuration si le réseau est recréé.

## 3. Ma relecture

| Élément relu | Ce que j'ai vérifié | Point restant | Référence |
|---|---|---|---|
| Dossier d'architecture S1 | J'ai lu la rédaction complète et vérifié qu'elle décrit le besoin, les cas d'usage et l'architecture visée. J'ai revu le classement du CSV : 4 lignes valides, 7 invalides et 1 doublon, conformément au sujet. | Confirmer les éventuelles bornes numériques supplémentaires dans le contrat détaillé. | `documents/architecture.md` §2, §5 et §9 |
| Code S2 | J'ai relu le code produit avec l'aide de l'IA après les contrôles automatisés et le parcours navigateur. | La reprise automatique d'un dépôt resté `running` après un arrêt brutal n'est pas réalisée ; les éventuelles bornes CSV supplémentaires restent à confirmer. | `api/app/`, `web/` et `proofs/s2-api-tests.txt` |

## 4. Usage d’outils d’IA

| Besoin d'aide | Aide reçue et mon usage | Ma vérification et sa limite |
|---|---|---|
| Comprendre l'énoncé et structurer la conception | L'assistant IA m'a aidé à rédiger `documents/architecture.md` ; je l'ai lu. L'assistant a ensuite classé les lignes du CSV avec erreurs, et j'ai revu ce classement. | Le document est une conception, pas une preuve de fonctionnement. Les éventuelles bornes CSV supplémentaires restent à confirmer dans le contrat détaillé. |
| Diagnostiquer la readiness à `503` | L'assistant m'a proposé des contrôles ; un premier test interne était trompeur et son diagnostic a été corrigé. J'ai exécuté `ALTER ROLE`. | J'ai revérifié `/health/ready` : `200`. Le premier test interne ne prouvait pas que l'API pouvait s'authentifier. |
| Terminer S2 | J'ai utilisé l'IA pour m'aider à avancer sur le code métier, le worker, l'interface et les tests d'intégration, puis j'ai relu le résultat. | Les tests, contrôles HTTP et parcours navigateur ont réussi. Je dois encore confirmer les éventuelles bornes CSV supplémentaires du contrat détaillé. |

Je reste responsable du code, des vérifications et du dossier remis.

## 5. Bilan final

Je compléterai mon bilan après les séances de développement et d'exploitation : une règle métier comprise, un incident diagnostiqué, une décision d'infrastructure expliquée et un point à approfondir. Aucun commit de code n'est attribué à l'incident DB : la correction a été faite dans PostgreSQL.
