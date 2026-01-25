# Agents Hub

Ce dossier contient les informations utiles pour de futures itérations assistées par Copilot.

- `AGENTS_CONTEXT.md` : vision produit & périmètre fonctionnel.
- `AGENTS_TECH.md` : choix techniques, bibliothèques et patterns utilisés.
- `AGENTS_OPERATIONS.md` : procédures d’exploitation, exécution et surveillance.
- `AGENTS_CODEMAP.md` : carte du code (user stories → modules → fichiers) pour naviguer vite.
- `AGENTS_SYNC_MONITORING.md` : deep dive synchro + requêtes Kibana prêtes à l’emploi.

Merci de maintenir ces fichiers à jour avant toute évolution majeure.

## Repères express par couche

- **API FastAPI (`app/api/…`)**
	- `routers/*.py` : endpoints REST par ressource (`sync`, `stats`, `alerts`, `google`, `email`).
	- `dependencies.py` : session SQLAlchemy, vérification du token admin, injection du scheduler.
	- `schemas.py` : Pydantic models partagés entre routes.
- **Clients externes (`app/clients/…`)**
	- `sirene_client.py` : appel REST Sirene + pagination `curseur`.
	- `google_places_client.py` : wrapper Places API + backoff (utilisé uniquement par GoogleBusinessService).
- **Services métier (`app/services/…`)**
	- Collecte : `sync_service.py` (orchestrateur), modules `sync/` (`collector.py`, `runner.py`, `persistence.py`) pour la fenêtre et la reprise, `establishment_mapper.py` (nettoyage), `sync_scheduler.py` et `incremental_scheduler.py` (cron interne).
	- Alertes & emails : `alert_service.py`, `email_service.py`, `client_service.py`, `export_service.py`.
	- Google : `google_business_service.py` pilote le backlog, `google_business/lookup_engine.py` fait les appels API, `constants.py` / `types.py` / `keywords.py` centralisent les briques communes.
	- Gouvernance : `rate_limiter.py` + `google_retry_config.py` (quotas, jours autorisés).
- **Données & utilitaires**
	- `app/db/models.py` : schéma complet (establishments, sync_runs, clients...).
	- `app/db/session.py` : ouverture de session + `init_db`.
	- `app/utils/*.py` : helpers transverses (dates, URLs, google listing, hashing, business_types).
- **Scripts & exploitation**
	- `scripts/deploy.sh` : déploiement (build image + apply migrations).
	- `scripts/extract_pdf_text.py` : extraction textuelle de la doc Sirene.
	- `sql/restore.sh` + `sql/backups` : restauration de dumps.
- **Tests**
	- `tests/test_google_business_service.py` : couverture du matching Google.
	- `tests/test_alert_service.py`, `test_admin_google_api.py`, `test_sync_collector_window.py` : garde-fous principaux.

> Astuce : combine ce mémo avec la table du `AGENTS.md` racine pour localiser rapidement un module avant d’ouvrir le fichier concerné.

## Code style & bonnes pratiques
Bien ajouter des logs, events, kpis sur les steps de logique, et s'assurer de créer des viz ou des dashboards de monitoring dans Kibana en modifiant le fichier docs/kibana/dashboards.ndjson.

### Discipline de refactor (anti code mort)
- Quand une logique est refactorée, supprimer **dans la même PR** les anciennes fonctions/classes, les flags/vars d'env devenus inutiles, et les champs/colonnes Kibana obsolètes.
- Vérifier via une recherche globale que les anciens noms ne subsistent plus (ex: `grep` sur le repo) et tenir à jour :
	- `docs/kibana/dashboards.ndjson` (et tout autre export versionné)
	- `.env.example` / docs associées
	- tests (supprimer/adapter ceux qui validaient l'ancienne voie)