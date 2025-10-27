# Exploitation & supervision

## Préparation
- Copier `.env.example` en `.env` et renseigner au minimum le token Sirene, la chaîne PostgreSQL (port local `15432`) et un `API__ADMIN_TOKEN` robuste.
- Lancer `docker compose up -d db` puis `python -m app init-db`.
- Optionnel : configurer l’envoi d’e-mails (`EMAIL__ENABLED=true` + SMTP).

## Exécutions
- **Initiale** : `python -m app sync-full` (reprend automatiquement si un run précédent a échoué).
- **Récurrente** : `python -m app sync-incremental` après vérification du `service informations` (script l’appel par défaut).
- **API admin** : `python -m app serve` (ou `make serve`) pour exposer les endpoints FastAPI. Vérifier que le reverse proxy ou le pare-feu restreint l’accès et que l’en-tête `X-Admin-Token` est fourni côté client.
- Les runs sont tracés dans `sync_runs` (status, métriques). Les curseurs et dates sont dans `sync_state`.
- Les logs applicatifs sont dans `logs/app.log`, les alertes dans `logs/alerts.log`.
- Les statistiques et états sont consultables via l’API (`GET /admin/stats/summary`, `/admin/sync-runs`, `/admin/sync-state`, `/admin/alerts/recent`).

## Relance / reprise
- En cas d’erreur, inspecter `sync_runs.status = 'failed'` et `sync_state.last_cursor`.
- Pour rejouer totalement la collecte : `python -m app sync-full --no-resume`.
- Pour purger proprement la base : arrêter le service, dropper les tables/postgres si nécessaire, relancer `init-db`.

## Supervision
- Surveiller :
  - Le quota API (réponses 429/503) dans `logs/app.log`.
  - La taille des tables (index sur `siret`, `code_postal`).
  - Le contenu des alertes (`alerts` + fichier) pour éviter les doublons.
- TODO futur : brancher un système d’alerting externe (Prometheus/Grafana, Sentry, etc.).
