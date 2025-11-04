# Exploitation & supervision

## Préparation
- Copier `.env.example` en `.env` et renseigner au minimum le token Sirene, la chaîne PostgreSQL (port local `15432`) et un `API__ADMIN_TOKEN` robuste.
- Lancer `docker compose up -d db` puis `python -m app init-db`.
- Optionnel : configurer l’envoi d’e-mails (`EMAIL__ENABLED=true` + SMTP).

## Exécutions
- **Initiale** : `python -m app sync --no-check-for-updates` pour forcer une collecte complète (reprend automatiquement si un run précédent a échoué).
- **Récurrente** : `python -m app sync --check-for-updates` afin de consulter le `service informations` et d’éviter un run si rien n’a changé. En production, l’API démarre un scheduler interne (`SyncScheduler`) qui applique la même vérification toutes les `sync.auto_poll_minutes` minutes, sous réserve du délai minimum `sync.minimum_delay_minutes` entre deux runs.
- **API admin** : `python -m app serve` (ou `make serve`) pour exposer les endpoints FastAPI. Vérifier que le reverse proxy ou le pare-feu restreint l’accès et que l’en-tête `X-Admin-Token` est fourni côté client.
- L’endpoint `/admin/sync` répond immédiatement (`202 Accepted`) en déclenchant le traitement en arrière-plan. Le statut initial du run est `pending`, le front réinterroge automatiquement l’API toutes les 5 s tant qu’un run reste actif.
- **Console web** : lancer `npm run dev` dans le projet `../biz-tracker-admin-ui` après `npm install`. L'URL par défaut `http://localhost:5173` doit être déclarée dans `API__ALLOWED_ORIGINS`.
- Les runs sont tracés dans `sync_runs` (status, métriques). Les curseurs et dates sont dans `sync_state`.
- Les logs applicatifs sont dans `logs/app.log`, les alertes dans `logs/alerts.log`.
- Les statistiques et états sont consultables via l’API (`GET /admin/stats/summary`, `/admin/sync-runs`, `/admin/sync-state`, `/admin/alerts/recent`).

## Relance / reprise
- En cas d’erreur, inspecter `sync_runs.status = 'failed'` et `sync_state.last_cursor`.
- Pour rejouer totalement la collecte : `python -m app sync --no-check-for-updates --no-resume`.
- Pour purger proprement la base : arrêter le service, dropper les tables/postgres si nécessaire, relancer `init-db`.

## Supervision
- Surveiller :
  - Le quota API (réponses 429/503) dans `logs/app.log`.
  - La taille des tables (index sur `siret`, `code_postal`).
  - Le contenu des alertes (`alerts` + fichier) pour éviter les doublons.
- Vérifier les erreurs front (console navigateur) en cas de problème CORS ; ajuster `API__ALLOWED_ORIGINS` le cas échéant.
- TODO futur : brancher un système d’alerting externe (Prometheus/Grafana, Sentry, etc.).
