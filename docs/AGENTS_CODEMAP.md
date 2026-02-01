# Carte du code (backend)

Objectif : permettre de localiser rapidement **où se trouve une fonctionnalité**, ce qui a déjà été implémenté, et **quel(s) fichier(s) ouvrir** avant toute modification.

## Comment utiliser ce fichier (surtout avec Copilot)

- Pour une demande “produit” (user story), partez de **Workflows (user stories)**.
- Pour une demande “API”, partez de **Routes HTTP** puis remontez vers les handlers/services.
- Pour une demande “pipeline sync”, partez de **Pipeline de synchronisation (Sirene → DB → Google → alertes)**.

## Entrées / cycle de vie de l’application

- **CLI** : `python -m app …`
  - Point d’entrée : `app/__main__.py` → `app/cli.py`.
  - Commandes clés : `init-db`, `sync`, `serve`.
- **API FastAPI** : factory `app/api/__init__.py:create_app`
  - Monte les routers : `health`, `admin`, `public`.
  - Ajoute les middlewares : access log + rate limiting.
- **Scheduler interne** : `app/services/sync_scheduler.py:SyncScheduler`
  - Démarre via le lifespan FastAPI.
  - **Désactivé si** `APP_ENVIRONMENT=local` ou `SYNC__AUTO_ENABLED=false`.

## Routes HTTP

### Public

- `GET /health` → `app/api/routers/health_router.py`
- `POST /public/contact` → `app/api/routers/public_router.py`
  - Utilisé par la landing page.
  - Honeypot anti-spam : champ `website` rempli ⇒ **accepté** mais **pas d’e-mail**.

### Admin (token requis)

Le router admin est dans `app/api/routers/admin/admin_router.py` (préfixe `/admin`).

- **Synchronisation** : `app/api/routers/admin/sync_runs_router.py`
  - `POST /admin/sync` déclenche un run (tâche de fond FastAPI).
  - `GET /admin/sync-runs` historique.
  - `GET /admin/sync-state` checkpoints.
  - `DELETE /admin/sync-runs/{run_id}` purge un run + données associées.
- **Établissements** : `app/api/routers/admin/establishments_router.py`
  - `GET /admin/establishments` (filtres `q`, `is_individual`).
  - `GET /admin/establishments/{siret}` détail.
  - `DELETE /admin/establishments/{siret}` suppression.
- **Alertes** : `app/api/routers/admin/alerts_router.py`
  - `GET /admin/alerts/recent`.
  - `GET /admin/alerts/export?days=…` (Excel basé sur `date_creation`).
- **Google** : `app/api/routers/admin/google_router.py`
  - `POST /admin/establishments/{siret}/google-check`.
  - `GET /admin/google/places-export` (Excel).
  - `GET/PUT /admin/google/retry-config`.
- **Stats** : `app/api/routers/admin/stats_router.py`
  - `GET /admin/stats/summary`.
  - `GET /admin/stats/dashboard?days=…`.
- **Email** : `app/api/routers/admin/email_router.py`
  - `POST /admin/email/test`.
  - `GET/PUT /admin/email/admin-recipients`.
- **Clients** : `app/api/routers/admin/clients_router.py` (+ handlers dédiés)
  - CRUD sur clients + recipients + subscriptions.
- **Catalogue NAF** : `app/api/routers/admin/naf_categories_router.py`
  - CRUD sur catégories et sous-catégories NAF (inclut `keywords` et `is_active`).

## Pipeline de synchronisation (Sirene → DB → Google → alertes)

Point d’orchestration : `app/services/sync_service.py` (compose des mixins).

- **Préparation / garde-fous**
  - `SyncService.prepare_sync_run(…)` : crée un `sync_run`, vérifie (optionnel) le service “informations”, vérifie qu’il n’y a pas déjà un run actif.
- **Exécution d’un run**
  - `SyncService.execute_sync_run(run_id, triggered_by=…)` (appelé par CLI, API ou scheduler).
  - La logique est répartie dans `app/services/sync/` :
    - `mode.py` : modes (`full`, `sirene_only`, `google_pending`, `google_refresh`, `day_replay`).
    - `collector.py` : collecte Sirene, pagination curseur, métriques, checkpoints.
    - `persistence.py` : upsert DB, liens `created_run_id` / `last_run_id`, détection updates.
    - `google_enrichment.py`, `google_only.py` : enrichissement Google selon le mode.
    - `day_replay.py`, `replay_reference.py` : rejeu d’une journée (sans perturber l’état global).
    - `summary.py` : résumé de run + e-mails admin.

Clients externes :
- Sirene : `app/clients/sirene_client.py`
- Google Places : `app/clients/google_places_client.py`

## Workflows (user stories) → où chercher quoi

- **Déclencher un run (UI/POST /admin/sync)**
  - Route : `app/api/routers/admin/sync_runs_router.py`
  - Pipeline : `app/services/sync_service.py` + `app/services/sync/*`
- **Auto-run (scheduler)**
  - Worker : `app/services/sync_scheduler.py`
  - Règles : `APP_ENVIRONMENT`, `SYNC__AUTO_*`, `SYNC__MINIMUM_DELAY_MINUTES`
- **Gérer le catalogue NAF (codes actifs, descriptions, keywords)**
  - Route : `app/api/routers/admin/naf_categories_router.py`
  - Modèle : `app/db/models.py` (`naf_categories`, `naf_subcategories`)
  - Validation : `app/utils/naf.py`
- **Configurer un client (période, statuts Google, destinataires)**
  - Routes : `app/api/routers/admin/clients_router.py`, `app/api/routers/admin/email_router.py`
  - Service : `app/services/client_service.py`
  - Modèles : `Client`, `ClientRecipient`, `ClientSubscription`
- **Enrichissement Google / exports**
  - Route export : `app/api/routers/admin/google_router.py` + `app/api/routers/admin/google_handlers.py`
  - Matching : `app/services/google_business/google_*` et `app/services/google_business/google_business_service.py`
  - Quotas/retry : `app/services/rate_limiter.py`, `app/services/google/google_retry_config.py`
- **Alertes & exports alertes**
  - Route : `app/api/routers/admin/alerts_router.py`
  - Génération : `app/services/alerts/alert_service.py`
  - Rendu e-mail : `app/services/alerts/email_renderer.py`
  - Export : `app/services/export_service.py`
- **Formulaire landing (/public/contact)**
  - Route : `app/api/routers/public_router.py`
  - E-mail : `app/services/email_service.py`

## Modèle de données (repères)

Définitions : `app/db/models.py`.

- `establishments` (PK = `siret`) : données Sirene + champs Google + timestamps de tracking.
- `sync_runs` (UUID) : exécutions, métriques, résumés, flags de rejeu.
- `sync_state` (PK = `scope_key`) : checkpoints (curseur, last_creation_date, last_treated_max…).
- `alerts` : alertes attachées à un `run_id` et à un `siret`.
- `clients`, `client_recipients`, `client_subscriptions` : configuration par client.
- `naf_categories`, `naf_subcategories` : catalogue pilotant le périmètre métier.
- `admin_recipients` : destinataires des résumés admin.
- `google_retry_config` : stratégie de relances Google.

## Invariants & “gotchas” (à connaître avant de modifier)

- **Auth admin** : dépendance `require_admin` dans `app/api/dependencies.py` (header configurable).
- **Sessions DB (API)** : `get_db_session()` commit automatiquement en fin de requête.
- **Docs OpenAPI** : `/docs` et `/redoc` désactivés par défaut (`API__DOCS_ENABLED`).
- **Google optionnel** : si `GOOGLE__API_KEY` est absent, aucune requête Google n’est émise.
- **Public rate limiting** : middleware global avec une policy plus stricte pour `/public/*`.
- **En local** : le scheduler interne ne démarre pas (`APP_ENVIRONMENT=local`).

## Tests (où regarder quand ça casse)

- Google : `tests/test_google_business_service.py`, `tests/test_admin_google_api.py`.
- Sync : `tests/test_sync_collector_window.py`, `tests/test_sync_request_schema.py`.
- Alertes / e-mails : `tests/test_alert_service.py`, `tests/test_email_service.py`, `tests/test_email_renderer.py`.
- API / middlewares : `tests/test_admin_*_router.py`, `tests/test_rate_limit_middleware.py`, `tests/test_access_log_middleware.py`.
- Public contact : `tests/test_public_contact_router.py`, `tests/test_public_contact_schema.py`.
