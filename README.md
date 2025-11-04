# Biz Tracker Back

Solution de veille sur les nouveaux établissements de restauration (NAF 56.10A) via l'API Sirene.

## Fonctionnalités principales
- Synchronisation complète initiale des établissements actifs (avec pagination `curseur` pour la stabilité).
- Synchronisations incrémentales quotidiennes basées sur `dateDernierTraitement*` et sur le service `informations`.
- Résilience : reprise automatique via `SyncState`, stockage des curseurs, gestion du throttling (30 appels/min).
- Détection des nouveaux SIRET et génération d'alertes (log fichier + e-mail configurable via SMTP).
- Traçabilité des exécutions (« moulinettes ») avec états, curseurs, métriques et possibilité de reprise.

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
   docker compose up -d db
   ```
4. **Créer votre fichier `.env`** à partir du template :
   ```bash
   cp .env.example .env
   ```
   Renseignez au minimum `SIRENE__API_TOKEN` et, si besoin, adaptez l’URL de base, la configuration SMTP ou les paramètres PostgreSQL.
5. **Initialiser la base** :
   ```bash
   python -m app init-db
   ```

## Commandes disponibles

Toutes les commandes passent par `python -m app …` (Typer).

| Commande | Description |
| --- | --- |
| `python -m app init-db` | Crée les tables si nécessaire. |
| `python -m app sync --check-for-updates` | Lance la synchronisation unifiée en vérifiant le service informations (annule si aucune nouveauté). |
| `python -m app sync --no-check-for-updates` | Force une synchronisation complète à partir du curseur courant. |
| `python -m app sync --no-check-for-updates --no-resume` | Rejoue intégralement la synchronisation depuis le début. |
| `python -m app serve` | Démarre l'API FastAPI sécurisée (admin token requis). |

Des cibles `Makefile` équivalentes existent (`make init-db`, `make sync`, `make serve`, `make sync-force`, etc.).

## API HTTP (admin seulement)

- Démarrage : `python -m app serve` (ou `make serve`). Par défaut, l'API écoute sur `0.0.0.0:8080` (configurable via `.env`).
- Authentification : chaque requête doit inclure l'en-tête `X-Admin-Token` (ou la valeur configurée) contenant le jeton défini dans `API__ADMIN_TOKEN`.
- Points d'entrée principaux :
   - `GET /health` : pong sans authentification, utile pour les probes.
   - `GET /admin/stats/summary` : synthèse des volumes et derniers runs.
   - `GET /admin/sync-runs` / `GET /admin/sync-state` / `GET /admin/alerts/recent` : monitoring détaillé.
   - `POST /admin/sync` (body `{ "resume": true, "check_for_updates": true }`) : déclenche une synchronisation unifiée (202 Accepted + `detail` si aucune nouveauté).
   - `DELETE /admin/sync-runs/{run_id}` : purge un run donné, supprime les établissements créés et les alertes associées, et réinitialise l’état de synchronisation lié.

Un fichier Postman de référence est disponible (`docs/postman_collection.json`). Pensez à définir la variable `baseUrl` et l'en-tête `X-Admin-Token` dans votre environnement Postman avant utilisation.

## Interface web d'administration

- Un projet React dédié (`biz-tracker-admin-ui`) vit à la racine du dossier parent du dépôt backend. Il consomme les endpoints `/admin/*` mentionnés ci-dessus.
- Installation côté UI :
   ```bash
   cd ../biz-tracker-admin-ui
   npm install
   cp .env.example .env  # adapter VITE_API_BASE_URL si besoin
   npm run dev
   ```
- L'interface écoute par défaut sur `http://localhost:5173`. Vérifiez que `API__ALLOWED_ORIGINS` dans `.env` côté backend contient cette origine (valeur par défaut fournie).
- Toute autre origine (hébergement distant, tunnel) peut être ajoutée à `API__ALLOWED_ORIGINS` sous forme de liste JSON ou de chaîne séparée par des virgules.

## Planification recommandée
- Exécuter `python -m app sync --no-check-for-updates` une seule fois pour amorcer la base.
- Programmer `python -m app sync --check-for-updates` quotidiennement **après** la publication des mises à jour Sirene (cf. `Service informations`).
   - La commande interroge `dateDernierTraitementMaximum`; si elle n’a pas évolué, elle s’arrête proprement.
   - En cas de mise à jour très volumineuse (`dateDernierTraitementDeMasse`), prévoyez un monitoring spécifique.

## Données stockées
- `establishments` : identité du SIRET (nom + fallbacks, adresse complète, dates, état, NAF 56.10A).
- `sync_runs` : journalisation de chaque moulinette (type, statut, métriques, curseur).
- `sync_state` : pointeurs pour la reprise (`curseur`, `dateDernierTraitementMaximum`, checksum de requête).
- `alerts` : traces des alertes envoyées (payload, destinataires, date d’envoi).

## Alertes e-mail & logs
- Les nouvelles entrées détectées lors d’une synchronisation sont loguées dans `logs/alerts.log`.
- Si l’envoi e-mail est activé (`EMAIL__ENABLED=true` + configuration SMTP), un message synthétique est expédié à la liste définie dans `EMAIL__RECIPIENTS`.

## Points d’attention
- L’API Sirene limite à 30 appels/minute : le client embarque un rate limiter et gère les réponses `429` / `503` avec back-off.
- La requête utilise le paramètre `curseur=*` puis `curseurSuivant` pour garantir l’ordre et éviter les doublons/omissions.
- Les champs demandés (`champs=`) sont réduits pour n’extraire que l’identification, les noms usuels/enseignes et l’adresse, conformément à la documentation.
- Les noms sont déterminés par priorisation (`denominationUsuelle`, `enseigne`, etc.) avec fallback sur les informations de l’unité légale.
- La reprise après incident se base sur `SyncState.last_cursor` pour la collecte complète, et sur `dateDernierTraitementMaximum` pour l’incrémental.

## Étapes suivantes
- Intégrer un monitoring (Prometheus, Sentry…) si nécessaire.
- Enrichir la partie notification (Slack, webhook) ou la recherche géographique (Google Maps) dans de futurs développements.

---
Ce README résume les choix d’implémentation ; les fichiers `docs/AGENTS_*.md` détaillent le contexte et les conventions pour les agents Copilot.
