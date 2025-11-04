# Choix techniques

- **Langage & runtime** : Python 3.11+, organisation modulaire (`app/clients`, `app/services`, `app/db`).
- **Config** : Pydantic Settings (v2) + `.env` avec séparateur `__` pour les sous-structures (ex. `SIRENE__API_TOKEN`). Paramètres API disponibles via `API__*` (host, port, header, admin token, activation des docs).
- **HTTP** : `requests` + `RateLimiter` logiciel + retry sur statuts 429/5xx (back-off exponentiel).
- **Persistence** : PostgreSQL (Docker Compose) + SQLAlchemy 2.0 (ORM classique).
  - Tables principales : `establishments`, `sync_runs`, `sync_state`, `alerts`.
  - Les objets sont créés via `app/db/models.py`; exécution des migrations simplifiée via `Base.metadata.create_all`.
- **Transformation** : `app/services/establishment_mapper.extract_fields` applique les règles métiers (fallbacks de nom, parsing dates/ISO).
- **Synchronisation** : `SyncService`
  - Collecte unifiée utilisant le curseur Sirene (`nombre=1000`) et limitée aux établissements créés dans les `sync.months_back` derniers mois (tri `dateCreationEtablissement desc`).
  - Déclenchements API exécutés en tâche de fond (FastAPI `BackgroundTasks`) avec un statut `pending` renvoyé immédiatement au front.
  - Possibilité de vérifier le `service informations` avant de lancer (`check_for_updates`) afin d’éviter un run s’il n’y a pas de nouveautés.
  - Scheduler interne (`SyncScheduler`) démarré avec l’API : scrute périodiquement les mises à jour (`sync.auto_poll_minutes`) et respecte un délai minimum `sync.minimum_delay_minutes` avant de relancer.
  - Reprise via `SyncState.last_cursor` et suivi des traitements via `SyncState.last_treated_max`.
- **Alertes** :
  - Logging dédié (`logging_config` définit un logger `alerts` -> `logs/alerts.log`).
  - Envoi SMTP optionnel (classe `EmailService`, désactivée si `EMAIL__ENABLED=false`).
- **API** : FastAPI (`app/api`) exposant des routes d’admin sécurisées par jeton (`X-Admin-Token` configurable). Les dépendances gèrent les sessions SQLAlchemy et les contrôles d’accès.
- **CORS** : middleware FastAPI activé. La liste des origines autorisées est configurable via `API__ALLOWED_ORIGINS` (liste JSON ou chaîne séparée par des virgules, valeur par défaut `http://localhost:5173`).
- **CLI** : Typer (`python -m app …`). Commandes `init-db`, `sync`, `serve` (lance Uvicorn). Aliases historiques `sync-full` et `sync-incremental` redirigent vers `sync`.
- **Tests & QA** : placeholder `make lint` (compileall). Prévoir pytest/ruff ultérieurement.

## UI d’administration

- Projet React + Vite (`biz-tracker-admin-ui`) placé hors du dépôt backend (dossier parent). S’appuie sur React Query pour appeler les endpoints `/admin/*`.
- Configuration via `.env` côté UI (`VITE_API_BASE_URL`). Build `npm run build`, dev `npm run dev` (port 5173).
