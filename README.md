# Business tracker Back

Solution de veille sur les nouveaux établissements de restauration (NAF 56.10A) via l'API Sirene.

## Documentation (à lire avant de modifier le code)

- Contexte, conventions et procédures : `docs/AGENTS_CONTEXT.md`, `docs/AGENTS_TECH.md`, `docs/AGENTS_OPERATIONS.md`.
- Carte de navigation du code (user stories → modules → fichiers) : `docs/AGENTS_CODEMAP.md`.

## Fonctionnalités principales
- Synchronisation complète initiale des établissements actifs (avec pagination `curseur` pour la stabilité).
- Synchronisations incrémentales quotidiennes basées sur `dateCreationEtablissement` (avec chevauchement configurable) et sur le service `informations`.
- Résilience : reprise automatique via `SyncState`, stockage des curseurs, gestion du throttling (30 appels/min).
- Détection des nouveaux SIRET et génération d'alertes (log fichier + e-mail configurable via SMTP).
- Traçabilité des exécutions (« moulinettes ») avec états, curseurs, métriques et possibilité de reprise.
- Agrégations journalières exposées via `GET /admin/stats/dashboard` (nouveaux établissements, appels API, alertes, statuts Google) et restituées dans l'interface React.

## Prérequis
- Python 3.11+
- Docker et Docker Compose pour la base PostgreSQL.
- Un token d’accès à l’API Sirene (`api.insee.fr`).
- (Optionnel) Ajuster `SIRENE__CURRENT_PERIOD_DATE` si vous devez rejouer l’historique à une date donnée. La
   valeur par défaut (`2100-01-01`) force l’API à retourner les valeurs courantes des champs historisés.

## Mise en route

1. **Cloner le dépôt** et créer un environnement virtuel Python (optionnel mais recommandé).
2. **Installer les dépendances** :
   ```bash
   pip install -r requirements.txt
   ```
3. **Configurer la base de données** via Docker (expose le port local `15432`) :
   ```bash
   docker compose up -d biz-tracker-db
   ```
   Si vous déployez l'API directement via Docker Compose (service `biztracker-back`), lancez immédiatement l'initialisation depuis le conteneur backend pour appliquer les migrations :
   ```bash
   docker compose exec biztracker-back python -m app init-db
   ```
4. **Créer votre fichier `.env`** à partir du template :
   ```bash
   cp .env.example .env
   ```
   Renseignez au minimum `SIRENE__API_TOKEN` et, si besoin, adaptez l’URL de base, la configuration SMTP ou les paramètres PostgreSQL. Définissez `APP_ENVIRONMENT=local` lorsque vous travaillez en développement afin de désactiver les synchronisations automatiques : seules les requêtes manuelles (`POST /admin/sync` ou `python -m app sync`) seront alors exécutées. Le champ `EMAIL__PROVIDER` permet de basculer rapidement entre `mailhog` (dev local), `mailjet` (production) ou `custom`. Pour activer l’enrichissement Google, renseignez `GOOGLE__API_KEY` avec une clé Places valide (voir section ci-dessous).
5. **Initialiser / mettre à niveau la base** :
   ```bash
   python -m app init-db
   ```
   Cette commande applique également les colonnes manquantes si vous avez mis à jour le projet.

## Exporter / restaurer la base PostgreSQL

1. **Générer un dump sur le serveur**
   1. Connectez-vous au serveur (`ssh user@host`) et placez-vous dans `biz-tracker-back/`.
   2. Assurez-vous que Docker Compose tourne (`docker compose ps`).
   3. Exécutez un dump logique (format custom recommandé) depuis le conteneur PostgreSQL :
      ```bash
      bash backup.sh
      ```
      (Les variables proviennent de `.env`. Adaptez-les si nécessaire.)

2. **Rapatrier le fichier en local**
  En local :
   ```bash
   scp root@145.223.118.21:./biz-tracker-back/backups/{filename} ./sql/backups
   ```

3. **Restaurer dans votre environnement local**
   1. Lancez votre PostgreSQL Docker (`docker compose up -d biz-tracker-db`).
   2. Chargez le dump soit depuis l'hôte, soit directement dans le conteneur :
      ```bash
      ./sql/restore.sh biz_tracker_db-backup-202511221748.sql.gz password_here
      ```
   3. Terminez par `python -m app init-db` si nécessaire pour appliquer les migrations locales.

## Commandes disponibles

Toutes les commandes passent par `python -m app …` (Typer).

| Commande | Description |
| --- | --- |
| `python -m app init-db` | Crée les tables si nécessaire. |
| `python -m app sync --check-for-updates` | Lance la synchronisation unifiée en vérifiant le service informations (annule si aucune nouveauté). |
| `python -m app sync --no-check-for-updates` | Force une synchronisation complète depuis le début. |
| `python -m app serve` | Démarre l'API FastAPI sécurisée (admin token requis). |

Des cibles `Makefile` équivalentes existent (`make init-db`, `make sync`, `make serve`, `make sync-force`, etc.).

## Tests & couverture

- Installer les dépendances de développement : `make install-dev` (équivalent à `pip install -r requirements-dev.txt`).
- Lancer la suite unitaire + couverture : `make test`. La configuration `pytest.ini` active automatiquement `pytest-cov` avec le seuil `95 %` défini dans `.coveragerc`.
- Le rapport terminal affiche aussi les fichiers manquants (`term-missing`) et génère `coverage.xml` (utile pour les outils CI / IDE).

Un workflow GitHub Actions (`.github/workflows/backend-tests.yml`) exécute ces étapes à chaque `push` / `pull request` impactant le dossier backend et bloque les déploiements sous le seuil requis.

## Pipeline de synchronisation

1. **Préparation du run** (`SyncService.prepare_sync_run`) : création d'un `sync_run` en statut `pending`, calcul du checksum de requête, option de vérification du service `informations` pour éviter un déclenchement inutile.
2. **Collecte Sirene** (`SyncService._collect_sync`) : itération `curseur` par `curseur`, respect du quota (30 appels/min) via `RateLimiter`, upsert des établissements et alimentation des métriques (`fetched_records`, `created_records`, `api_call_count`).
3. **Enrichissement Google** (`GoogleBusinessService.enrich`) : constitution d'une file (nouveautés + backlog), filtrage des identités insuffisantes, appels `find_place` / `get_place_details` sous rate limiting, mise à jour des colonnes Google et des compteurs (`google_*`).
4. **Alerting** (`AlertService.create_google_alerts`) : création des entrées `alerts`, logging structuré et envoi SMTP si la configuration est valide et qu'un run précédent a déjà abouti.
5. **Finalisation** (`SyncService._finish_run`) : passage du run en `success`, mise à jour des curseurs `SyncState` (curseur Sirene, `dateDernierTraitementMaximum`, `last_creation_date`). En cas d'exception, rollback et statut `failed` garantissent la reprise.

Le scheduler (`SyncScheduler`) applique cette séquence automatiquement selon `sync.auto_poll_minutes`, tout en respectant `sync.minimum_delay_minutes` entre deux exécutions. Il se désactive automatiquement lorsque `APP_ENVIRONMENT=local` pour éviter tout déclenchement implicite en développement.

## API HTTP (admin seulement)

- Démarrage : `python -m app serve` (ou `make serve`). Par défaut, l'API écoute sur `0.0.0.0:8080` (configurable via `.env`).
- Authentification : chaque requête doit inclure l'en-tête `X-Admin-Token` (ou la valeur configurée) contenant le jeton défini dans `API__ADMIN_TOKEN`.
- Points d'entrée principaux :
   - `GET /health` : pong sans authentification, utile pour les probes.
   - `GET /admin/stats/summary` : synthèse des volumes et derniers runs.
   - `GET /admin/stats/dashboard` : agrégations journalières (nouveaux établissements, appels API, alertes, statuts Google et répartition par état administratif).
   - `GET /admin/sync-runs` / `GET /admin/sync-state` / `GET /admin/alerts/recent` : monitoring détaillé.
   - `POST /admin/sync` (body `{ "check_for_updates": true }`) : déclenche une synchronisation unifiée (202 Accepted + `detail` si aucune nouveauté).
   - `DELETE /admin/sync-runs/{run_id}` : purge un run donné, supprime les établissements créés et les alertes associées, et réinitialise l’état de synchronisation lié.

Un fichier Postman de référence est disponible (`docs/postman_collection.json`). Pensez à définir la variable `baseUrl` et l'en-tête `X-Admin-Token` dans votre environnement Postman avant utilisation.

## Interface web d'administration

- Un projet React dédié (`biz-tracker-admin-ui`) vit à la racine du dossier parent du dépôt backend. Il consomme les endpoints `/admin/*` mentionnés ci-dessus.
- Installation côté UI :
   ```bash
   cd ../biz-tracker-admin-ui
   npm install
   cp .env.example .env  # adapter VITE_APP_API_BASE_URL si besoin
   npm run dev
   ```
- L'interface écoute par défaut sur `http://localhost:5173`. Vérifiez que `API__ALLOWED_ORIGINS` dans `.env` côté backend contient cette origine (valeur par défaut fournie).
- Toute autre origine (hébergement distant, tunnel) peut être ajoutée à `API__ALLOWED_ORIGINS` sous forme de liste JSON ou de chaîne séparée par des virgules.
- La section « Monitoring quotidien » de l'UI consomme `GET /admin/stats/dashboard` pour restituer les courbes journalières (nouveaux établissements, appels API), la répartition Google (global et dernier run), les alertes envoyées et le bilan des statuts établissements.

## Proxy Nginx (whitelist IP)

Le backend est souvent exposé via `jwilder/nginx-proxy` + `letsencrypt-nginx-proxy-companion`. Pour restreindre certains hôtes ou chemins a une IP precise, placez un fichier par hostname dans `vhost.d`.

1. Sur l'hote, creez un dossier persistant et montez-le dans les deux services nginx-proxy (exemple):
   ```bash
   mkdir -p /srv/nginx-proxy/vhost.d
   ```
   ```yaml
   volumes:
     - /srv/nginx-proxy/vhost.d:/etc/nginx/vhost.d
   ```
2. Creez un fichier par hostname, par exemple:
   - `/srv/nginx-proxy/vhost.d/admin.business-tracker.fr`
   - `/srv/nginx-proxy/vhost.d/kibana.business-tracker.fr`
   - `/srv/nginx-proxy/vhost.d/api.business-tracker.fr`
3. Pour un hostname entier (admin / kibana), un allow/deny suffit:
   ```nginx
   allow 12.34.56.78;
   deny all;
   ```
4. Pour restreindre uniquement `/admin` sur `api.business-tracker.fr`, il faut conserver le proxy_pass genere par nginx-proxy. Recuperez l'upstream dans la config effective:
   ```bash
   docker exec nginx-proxy nginx -T | sed -n '/server_name api.business-tracker.fr/,/}/p'
   ```
   Copiez la valeur de `proxy_pass http://...;` et utilisez-la dans le fichier:
   ```nginx
   location = /admin {
     allow 12.34.56.78;
     deny all;

     proxy_pass http://api.business-tracker.fr;
     proxy_set_header Host $host;
     proxy_set_header X-Real-IP $remote_addr;
     proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
     proxy_set_header X-Forwarded-Proto $scheme;
   }

   location ^~ /admin/ {
     allow 12.34.56.78;
     deny all;

     proxy_pass http://api.business-tracker.fr;
     proxy_set_header Host $host;
     proxy_set_header X-Real-IP $remote_addr;
     proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
     proxy_set_header X-Forwarded-Proto $scheme;
   }
   ```
5. Rechargez nginx:
   ```bash
   docker exec nginx-proxy nginx -t
   docker exec nginx-proxy nginx -s reload
   ```

Si vous passez par un CDN (ex: Cloudflare), configurez `real_ip_header` et `set_real_ip_from` pour que Nginx voie l'IP cliente reelle, sinon la whitelist ne marchera pas.

## Planification recommandée
- Exécuter `python -m app sync --no-check-for-updates` une seule fois pour amorcer la base (chaque exécution rejoue l'intégralité de la collecte).
- Programmer `python -m app sync --check-for-updates` quotidiennement **après** la publication des mises à jour Sirene (cf. `Service informations`).
   - La commande interroge `dateDernierTraitementMaximum`; si elle n’a pas évolué, elle s’arrête proprement.
   - En cas de mise à jour très volumineuse (`dateDernierTraitementDeMasse`), prévoyez un monitoring spécifique.
   - Le chevauchement `SYNC__CREATION_OVERLAP_DAYS` rejoue N jours autour du dernier `last_creation_date` pour capter des arrivées tardives sans retraiter tout l’historique.

## Données stockées
- `establishments` : identité du SIRET (nom + fallbacks, adresse complète, dates, état, NAF 56.10A).
- `sync_runs` : journalisation de chaque moulinette (type, statut, métriques, curseur).
- `sync_state` : pointeurs pour la reprise (`curseur`, `dateDernierTraitementMaximum`, `last_creation_date`, checksum de requête).
- `alerts` : traces des alertes envoyées (payload, destinataires, date d’envoi).

## Alertes e-mail & logs
- Les nouvelles entrées détectées lors d’une synchronisation sont loguées dans `logs/alerts.log`.
- Si l’envoi e-mail est activé (`EMAIL__ENABLED=true` + configuration SMTP), un message synthétique est expédié aux destinataires actifs configurés pour chaque client (table `client_recipients`).
- Une synthèse quotidienne de run est envoyée aux destinataires administrateurs gérés via `/admin/email/admin-recipients` (table `admin_recipients`).
- Presets disponibles : `EMAIL__PROVIDER=mailhog` (hôte `localhost`, port `1025`, TLS désactivé, interface http://localhost:8025 via `docker compose up -d biz-tracker-mailhog`), `EMAIL__PROVIDER=mailjet` (hôte `in-v3.mailjet.com`, port `587`, TLS activé, identifiant = API key, mot de passe = secret key), `EMAIL__PROVIDER=custom` (remplir manuellement `EMAIL__SMTP_*`).
- L’endpoint `POST /admin/email/test` déclenche un envoi de test (corps optionnel) afin de valider la configuration active.

## Observabilité Kibana
- Un handler Elasticsearch optionnel peut être activé via `.env` (`LOGGING__ELASTICSEARCH__ENABLED=true`). Les autres variables `LOGGING__ELASTICSEARCH__HOSTS`, `LOGGING__ELASTICSEARCH__INDEX_PREFIX`, `LOGGING__ELASTICSEARCH__ENVIRONMENT` et `LOGGING__ELASTICSEARCH__USERNAME`/`PASSWORD` ajustent la connexion.
- Lancer `docker compose up -d biz-tracker-elasticsearch biz-tracker-kibana` pour démarrer la pile locale (Elasticsearch : `http://localhost:9200`, Kibana : `http://localhost:5601`).
- Importer le fichier `docs/kibana/dashboards.ndjson` depuis Kibana (Stack Management > Saved Objects) pour obtenir un dashboard clef en main : runs terminés/en échec, nouveaux établissements, alertes Google.
- Les événements (`event.name`) exposent toutes les métriques : `sync.run.*`, `sync.new_establishment`, `sync.google.*`, `sync.updated_establishment*`, `sync.alert.created`, `alerts.email.*`, `sync.summary.email.*`, `scheduler.*`, `email.test_sent`. Ils peuvent être utilisés pour créer de nouvelles visualisations Lens (comparaison avec les agrégations `GET /admin/stats/dashboard`, temps moyen, volumétrie journalière, etc.).

## Enrichissement Google Places
- Activez l’enrichissement en renseignant `GOOGLE__API_KEY` (clé Places API) dans `.env`. Les autres paramètres (`GOOGLE__FIND_PLACE_URL`, `GOOGLE__PLACE_DETAILS_URL`, quotas, langue…) disposent de valeurs par défaut mais peuvent être surchargés.
- La clé doit disposer au minimum des API **Places API** et **Geocoding API**, avec un mode de facturation actif. Restriction recommandée : limiter la clé aux IP/host applicatifs et aux API nécessaires.
- Lorsqu’elle est absente, le service `GoogleBusinessService` est désactivé automatiquement et aucun appel n’est tenté (les runs restent fonctionnels sans enrichissement).

## Points d’attention
- L’API Sirene limite à 30 appels/minute : le client embarque un rate limiter et gère les réponses `429` / `503` avec back-off.
- La requête utilise le paramètre `curseur=*` puis `curseurSuivant` pour garantir l’ordre et éviter les doublons/omissions.
- Les champs demandés (`champs=`) sont réduits pour n’extraire que l’identification, les noms usuels/enseignes et l’adresse, conformément à la documentation.
- Les noms sont déterminés par priorisation (`denominationUsuelle`, `enseigne`, etc.) avec fallback sur les informations de l’unité légale.
- La reprise après incident se base sur `SyncState.last_cursor` pour la collecte complète, et sur `last_creation_date` pour limiter la fenêtre `dateCreationEtablissement` des incrémentaux (avec chevauchement configurable).

## Étapes suivantes
- Intégrer un monitoring (Prometheus, Sentry…) si nécessaire.
- Enrichir la partie notification (Slack, webhook) ou la recherche géographique (Google Maps) dans de futurs développements.

---
Ce README résume les choix d’implémentation ; les fichiers `docs/AGENTS_*.md` détaillent le contexte et les conventions pour les agents Copilot.

Voir tailles des logs Docker :
find /var/lib/docker/containers/ -name "*.log" -type f -exec du -h {} + | sort -h

Vider logs Docker :
find /var/lib/docker/containers/ -name "*-json.log" -type f -exec truncate -s 0 {} \;

docker compose exec biztracker-back python -m app init-db
