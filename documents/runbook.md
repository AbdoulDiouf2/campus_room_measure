# Exploitation CampusData

**Équipe / responsable :** à renseigner. **Dernière vérification :** à renseigner.
Ce document doit permettre à un autre binôme d’intervenir sans explication orale.
Chaque procédure précise contexte, préconditions, action, attendu, contrôle et
retour à l’état normal. Ne jamais coller un **secret** dans les exemples.

## 1. Inventaire

| Ressource | Identifiant non **secret** | Région/contexte | Propriétaire | Rôle | Suppression prévue |
|---|---|---|---|---|---|
| À renseigner | Valeur relevée | Environnement | Équipe | Utilité | Date/procédure |

Consigner VM, **volume**, groupe de sécurité, clé publique référencée, **namespace**,
**images** API/web et digests. Distinguer ressources propres et ressources partagées.
Documenter où les secrets sont conservés sans copier leur valeur.

## 2. Vérifications avant intervention

- Poste ou VM et dossier de travail : à préciser pour chaque commande.
- Cluster/contexte et **namespace** : à contrôler avant mutation.
- Version actuelle et version visée : à relever avant promotion.
- État DB, **jeu témoin** et **sauvegarde** utile : à vérifier.
- Effet attendu, risque d’interruption et condition d’arrêt : à expliquer.

## 3. Déployer une version

Décrire prérequis, **images** disponibles, rendu de l’overlay, transfert et application.
Préciser quand initialiser le schéma et pourquoi ne pas attendre une **readiness**
métier qui dépend d’une table pas encore créée.

| Étape | Lieu/dossier | Commande adaptée | Attendu | Contrôle si échec |
|---|---|---|---|---|
| À renseigner | Poste ou VM | **Sans secrets** | Observation | Diagnostic ciblé |

Conclure avec versions API/web, **rollout**, dépôt traité et données préexistantes retrouvées.
Une ressource créée n’est pas une preuve suffisante de **service** prêt.

### Fiche de release

Remplir une fiche par version promue ou restaurée. Une release n’est « promue »
que si les quatre contrôles de la dernière ligne sont observés.

| Élément | Release précédente | Release candidate |
|---|---|---|
| Commit source des images | À relever | À relever |
| Run CI (lien) et résultat | À relever | À relever |
| Image API : tag et digest | À relever | À relever |
| Image web : tag et digest | À relever | À relever |
| Commit de configuration (overlay) | À relever | À relever |
| Changement visible pour la distinguer | À décrire | À décrire |
| Heure d’application et opérateur | À relever | À relever |
| Rollout API/web, `/api/version`, parcours métier, jeu témoin | Observé / non observé | Observé / non observé |

### Déploiement local S3 vérifié le 26/11/2026

Lieu : serveur `maadec-infra-01`, racine du dépôt. Charger `.env` dans **chaque nouveau terminal** et vérifier sans afficher le secret que l’hôte de `DATABASE_URL` est `db`. Arrêter les services systemd et la pile `compose.dev.yaml` pour libérer 8080, sans `down -v`. Construire API/web avec `APP_VERSION=$(git rev-parse HEAD)` ; démarrer DB avec `up -d --wait db`, lancer `run --rm --no-deps api python -m app.init_db`, puis `up -d api worker web`. Vérifier `docker compose -f compose.yaml ps`, `/health/ready`, `/api/version`, dépôt traité et jeu témoin. Le volume durable S3 observé est `campusdata_pgdata`, distinct du volume de développement. Une recréation avec `down` **sans `-v`** a conservé le jeu `bedb6cda-1110-4d52-ad5c-876a99f244a9` et ses 63 mesures. La preuve détaillée est `proofs/s3-persistance.txt`.

## 4. Diagnostiquer un incident

Suivre : symptôme - hypothèse - commande - observation - correction - contrôle.
Distinguer navigateur, tunnel, **Nginx**, **Service**, **Pod**, API et PostgreSQL.

| Symptôme | Hypothèse | Observation discriminante | Correction ciblée | Vérification de reprise |
|---|---|---|---|---|
| À renseigner | Cause possible | Ce qui la confirme ou l’infirme | Action justifiée | Effet utilisateur |

Conserver heure, durée et dernière modification. Éviter une réinstallation
ou suppression de stockage avant d’avoir compris l’état des données.

### Fiche d’incident

| Rubrique | Contenu attendu |
|---|---|
| Début / fin / durée | Heures relevées, pas estimées après coup |
| Symptôme utilisateur | Ce que voit le navigateur ou `curl` (code HTTP, message) |
| État observé | Pods, événements, rollout, logs utiles, sans secret |
| Hypothèse et preuve | Hypothèse retenue et observation qui la confirme |
| Hypothèses infirmées | Pistes écartées et raison |
| Correction | Commande ou modification appliquée, lieu d’exécution |
| Contrôle de reprise | Readiness, version API/web, lecture du jeu témoin |
| Condition d’arrêt | Ce qui aurait imposé d’arrêter (mauvais cluster, risque sur les données) |
| Suite à donner | Amélioration du runbook, test ou alerte à ajouter |

### Incident local S3 observé le 26/11/2026

Symptôme initial : `init_db` dans le conteneur API refusait la connexion à `127.0.0.1:5432`, malgré une DB healthy. Cause : `DATABASE_URL` du `.env` pointait vers la loopback du poste ; dans un conteneur, cette adresse pointe sur le conteneur lui-même. Correction : mettre l’hôte `db` dans le `.env`, **recharger `.env` dans le terminal**, relancer `init_db` ; contrôle : API healthy et `/health/ready` 200. La première relecture de persistance n’affichait rien car la variable `S3_DATASET_ID` était vide dans un nouveau terminal ; reprendre l’UUID conservé dans `proofs/s3-worker.txt` et exiger un `GET` 200 avec le même compteur avant de conclure.

Panne volontaire : `docker compose -f compose.yaml stop db` a laissé `/health/live` à 200 mais `/health/ready` et `/api/datasets` sont passés à 503. Après `start db`, readiness 200 et 63 mesures relues sur le témoin. Voir `proofs/s3-panne-db.txt`. Retour à l’état normal : quatre services actifs, DB/API healthy, même UUID de jeu et même nombre de mesures ; ne jamais supprimer `campusdata_pgdata` pour corriger une panne.

## 5. Revenir à la version précédente

Relever les anciennes **images** API ET web et la configuration correspondante.
Vérifier la compatibilité de schéma, appliquer le retour et contrôler les deux
composants ainsi que le **jeu témoin**. Expliquer la différence entre réparer un
**rollout** avec une image invalide et restaurer une release précédente.

Si une commande impérative est utilisée, réconcilier ensuite les fichiers
versionnés avec l’état souhaité. Un **rollback** d’**image** n’annule pas une migration SQL.

## 6. Sauvegarder et restaurer

Préciser base source, format, destination VM, copie hors VM et droits d’accès.
Expliquer où sont interprétées les redirections shell et pourquoi aucun TTY
ne doit modifier le flux binaire de **sauvegarde**.

Décrire la **restauration** dans une **base distincte** puis la comparaison d’un témoin :
identifiant du jeu, nombre de mesures, somme de contrôle et période couverte. Exiger une ligne retrouvée, pas deux résultats vides.
Consigner résultat, durée et bornes du chronométrage.

- **RPO** expliqué pour cette **sauvegarde** ponctuelle : à renseigner.
- **RTO** visé et durée réellement mesurée : à renseigner séparément.
- Limite de la **restauration** sur le même serveur : à expliquer.
- Extension éventuelle sur serveur neuf : **résultat réel** ou non exécuté.

## 7. Reprendre après arrêt

Décrire récupération d’une nouvelle IP éventuelle, vérification du service **K3s**,
définition de la fonction kubectl sur VM, état Pods/PVC, tunnel et **jeu témoin**.
Ne pas régénérer le mot de passe d’une DB existante par simple relance du bloc
initial de création de Secret.

## 8. Clôturer et contrôler les ressources

Exporter preuves et sauvegardes utiles avant suppression. Identifier l’instance
et les volumes exacts ; suivre la procédure de la séance 6. Distinguer Stop,
Terminate et traitement des volumes, snapshots ou adresses conservés.

| Ressource du TP | État avant | Action de clôture | État vérifié après | Preuve/date | Exception justifiée |
|---|---|---|---|---|---|
| À renseigner | Relevé | Action ciblée | Constat | Référence | Si nécessaire |

Préciser ressources partagées conservées, révocation des accès temporaires et
vérification différée des coûts. Ne pas conclure à une clôture sur la seule
fermeture du **tunnel SSH**.

## Comment rédiger une commande réutilisable

Pour chaque bloc, ajoutez un commentaire indiquant poste ou VM, dossier de départ,
variables nécessaires et effet attendu. Une personne qui ouvre un nouveau terminal
doit savoir quoi recharger. Indiquez aussi comment quitter un suivi -w ou un tunnel,
et distinguez cela de l’arrêt du **service** observé.

Pour une opération sur une base, un **volume** ou une ressource cloud, nommez la cible
et la vérification préalable. Placez le contrôle de résultat immédiatement après
l’action, avec une piste de diagnostic si ce contrôle échoue.
