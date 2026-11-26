# CampusData

CampusData importe des fichiers CSV de capteurs (CO₂, température, humidité), conserve les mesures par salle dans PostgreSQL et affiche les indicateurs d'un jeu de données. L'API enregistre un dépôt en `pending` avec une réponse HTTP `202` ; un worker distinct traite ensuite le CSV et produit le rapport des lignes acceptées, rejetées et en doublon. Le prototype n'a pas d'authentification.

## État du projet

Le code métier, le worker, l'interface et les tests d'intégration de S2 sont présents. Les contrôles automatisés sur `campus_test` passent (`14 passed` au 26/11/2026). La page et l'API répondent via Nginx sur le serveur de développement. **Le parcours visuel au navigateur et au clavier a été contrôlé sur le serveur de développement ; voir `proofs/s2-api-tests.txt`.** Les déploiements Compose complet, Kubernetes, AWS, CI et restauration des séances S3–S6 n'ont pas encore été validés.

Le kit de départ a fourni les Dockerfiles, Compose, manifestes Kubernetes, trames documentaires et trois CSV. Les modules métier de `api/app/`, l'interface et les tests S2 ont été ajoutés pendant le projet.

## Architecture

- `web/` : page HTML/CSS/JavaScript servie par Nginx. Le navigateur appelle `/api` sur la même origine.
- `api/` : FastAPI, validation des requêtes, opérations métier et réponses HTTP.
- `python -m app.worker` : traite les dépôts en boucle ; `--once` vide la file courante puis termine, pour le CronJob Kubernetes.
- PostgreSQL : tables `datasets`, `ingestions`, `measurements`. Le CSV brut est stocké avec son dépôt afin que le worker puisse le lire sans disque partagé.

Le réseau de développement expose PostgreSQL sur `127.0.0.1:5432` et le web sur `127.0.0.1:8080`. L'API écoute sur la passerelle Docker du serveur pour que le proxy web puisse l'atteindre. En Compose complet et Kubernetes, la base et l'API doivent rester internes.

## Démarrage S1–S2 sur le serveur de développement

Les commandes ci-dessous partent de la racine du dépôt. Python 3.12, Docker Compose et le venv `.aivancity-venv` sont nécessaires. Créer `.env` à partir de `.env.example` avec un mot de passe local ; ne jamais le versionner.

```bash
source .aivancity-venv/bin/activate
set -a; source .env; set +a
docker compose -f compose.dev.yaml up -d db web
export DATABASE_URL="postgresql+psycopg://${POSTGRES_USER}:${POSTGRES_PASSWORD}@127.0.0.1:5432/${POSTGRES_DB}"
cd api
python -m app.init_db
```

Sur ce serveur, `compose.dev.yaml` résout `host.docker.internal` vers `172.26.0.1`. L'API et le worker sont lancés par deux services systemd utilisateur, activés au démarrage de la session et maintenus après sa fermeture (`Linger=yes`). Ils restent donc actifs quand l'IDE est fermé. Leur état se vérifie ainsi :

```bash
systemctl --user status campusdata-api.service campusdata-worker.service
journalctl --user -u campusdata-api.service -u campusdata-worker.service -n 50 --no-pager
```

Après une modification du code Python, redémarrer le ou les services concernés avec `systemctl --user restart campusdata-api.service campusdata-worker.service`. Les unités versionnées sont dans `systemd/` et leurs scripts de lancement dans `scripts/`. Sur une autre machine, adapter les chemins absolus et la passerelle Docker avant de lier ces unités avec `systemctl --user link` puis de les activer avec `systemctl --user enable --now`.

L'adresse `172.26.0.1` est propre au réseau Docker actuel du serveur. Si ce réseau change, relever sa passerelle, adapter `extra_hosts`, le script API et la règle UFW limitée au réseau de développement. Une connexion directe à l'API sur `127.0.0.1:8000` ne fonctionnera pas avec ce mode d'écoute ; utiliser le point d'entrée web.

Dans un autre terminal sur le serveur :

```bash
curl http://127.0.0.1:8080/health/live
curl http://127.0.0.1:8080/health/ready
curl http://127.0.0.1:8080/api/version
```

La page est disponible sur `http://127.0.0.1:8080/` depuis le serveur. Le relais Tailscale configuré sur ce serveur donne aussi `https://maadec-infra-01.tailebc8ae.ts.net:8444/` aux membres autorisés du tailnet.

Le service `campusdata-worker.service` traite les dépôts en continu. La commande `python -m app.worker --once`, exécutée depuis `api/` avec `DATABASE_URL` configuré, vide la file courante puis se termine pour le CronJob Kubernetes. Un dépôt déjà `running` lors d'un arrêt brutal n'est pas repris automatiquement dans cette version.

## Vérifications S2

Les tests d'intégration utilisent **uniquement** une base nommée `campus_test`, initialisée avec `python -m app.init_db` sous un `DATABASE_URL` pointant vers cette base. Ne jamais lancer ces tests sur `campus`.

```bash
source .aivancity-venv/bin/activate
set -a; source .env; set +a
export DATABASE_URL="postgresql+psycopg://${POSTGRES_USER}:${POSTGRES_PASSWORD}@127.0.0.1:5432/campus_test"
cd api
python -m app.init_db
cd ..
python -m ruff check api
python -m pytest -q
node --check web/app.js
```

Les trois CSV de `data/` servent à la recette : fichier valide → 63 acceptées ; fichier mixte → 4 acceptées, 7 rejetées, 1 doublon ; en-tête invalide → `failed` et 0 mesure. Un second dépôt du fichier valide donne 0 acceptée et 63 doublons, avec toujours 63 mesures dans le jeu.

## Contrat HTTP principal

| Méthode | Chemin | Résultat |
|---|---|---|
| POST | `/api/datasets` | Crée un jeu (`201`) ; nom déjà pris `409` |
| GET | `/api/datasets`, `/api/datasets/{id}` | Liste et détail avec `measurement_count` |
| DELETE | `/api/datasets/{id}` | Supprime jeu et données liées (`204` sans corps) |
| POST | `/api/datasets/{id}/ingestions?filename=...` | CSV brut `text/csv`, 1 Mio max ; dépôt `pending` (`202`) |
| GET | `/api/datasets/{id}/ingestions`, `/api/ingestions/{id}` | Liste et rapport des dépôts |
| POST | `/api/ingestions/{id}/retry` | Relance un dépôt `failed` (`202`) ; autre statut `409` |
| GET | `/api/datasets/{id}/stats?room=&from=&to=` | Indicateurs par salle et période |

Un dépôt à en-tête correct peut finir `succeeded` avec des lignes rejetées. Une erreur d'en-tête ou d'encodage rend le dépôt `failed`. La clé unique `(dataset_id, room, measured_at)` empêche les mesures en doublon entre dépôts.

## Documents et limites

- `documents/architecture.md` : besoin, conception, données et décisions.
- `documents/recette.md` : résultats observés et opérations restant à faire.
- `documents/journal.md` : travail et incidents.
- `proofs/` : sorties expurgées. Ne pas y mettre de mot de passe, DSN complet, clé ou dump.
- `documents/runbook.md` : trame d'exploitation à compléter lors des séances suivantes.

`create_all` crée les tables absentes, mais ne remplace pas un système de migrations. Le traitement d'un dépôt resté `running` après un arrêt brutal et les déploiements S3–S6 restent à vérifier. Ne pas supprimer le volume PostgreSQL avant d'avoir sauvegardé les données utiles.
