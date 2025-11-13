# Exploitation & supervision

## Préparation
- Copier `.env.example` en `.env` et renseigner au minimum le token Sirene, la chaîne PostgreSQL (port local `15432`) et un `API__ADMIN_TOKEN` robuste.
- Lancer `docker compose up -d biz-tracker-db` puis `python -m app init-db` (rejouer après chaque mise à jour pour appliquer les colonnes manquantes).
- Optionnel : configurer l’envoi d’e-mails (`EMAIL__ENABLED=true` + SMTP). Utiliser `EMAIL__PROVIDER=mailhog` en local (lancer `docker compose up -d biz-tracker-mailhog`, interface http://localhost:8025) et `EMAIL__PROVIDER=mailjet` en production (identifiant = API key, mot de passe = secret key, expéditeur validé côté Mailjet).
- Optionnel : activer l’enrichissement Google Places en définissant `GOOGLE__API_KEY` (clé API avec Places + Geocoding activées et facturation). Sans clé, le service reste inactif.

## Exécutions
- **Initiale** : `python -m app sync --no-check-for-updates` pour forcer une collecte complète (chaque run repart désormais de zéro).
- **Récurrente** : `python -m app sync --check-for-updates` afin de consulter le `service informations` et d’éviter un run si rien n’a changé. En production, l’API démarre un scheduler interne (`SyncScheduler`) qui applique la même vérification toutes les `sync.auto_poll_minutes` minutes, sous réserve du délai minimum `sync.minimum_delay_minutes` entre deux runs.
- **API admin** : `python -m app serve` (ou `make serve`) pour exposer les endpoints FastAPI. Vérifier que le reverse proxy ou le pare-feu restreint l’accès et que l’en-tête `X-Admin-Token` est fourni côté client.
- L’endpoint `/admin/sync` répond immédiatement (`202 Accepted`) en déclenchant le traitement en arrière-plan. Le statut initial du run est `pending`, le front réinterroge automatiquement l’API toutes les 5 s tant qu’un run reste actif.
- **Console web** : lancer `npm run dev` dans le projet `../biz-tracker-admin-ui` après `npm install`. L'URL par défaut `http://localhost:5173` doit être déclarée dans `API__ALLOWED_ORIGINS`.
- Les runs sont tracés dans `sync_runs` (status, métriques). Les curseurs et dates sont dans `sync_state`.
- Les logs applicatifs sont dans `logs/app.log`, les alertes dans `logs/alerts.log`.
- Les statistiques et états sont consultables via l’API (`GET /admin/stats/summary`, `/admin/stats/dashboard`, `/admin/sync-runs`, `/admin/sync-state`, `/admin/alerts/recent`).
- `POST /admin/email/test` permet de vérifier la configuration SMTP active (destinataires admin par défaut, sinon clients actifs ou ceux fournis dans le corps de la requête).
- `GET /admin/google/places-export` retourne un export Excel des établissements disposant d’une fiche Google (utilisé après la première synchronisation massive).
- L’enrichissement Google journalise `sync.google.*`; surveiller les quotas et les éventuelles réponses `OVER_QUERY_LIMIT` côté logs applicatifs.
- À la fin de chaque run réussi, une synthèse texte est envoyée aux entrées `admin_recipients` (si le service e-mail est actif et configuré). Le message récapitule les volumes récupérés, les mises à jour, les correspondances Google immédiates vs tardives et les principales alertes.

## Relance / reprise
- En cas d’erreur, inspecter `sync_runs.status = 'failed'` et `sync_state.last_cursor`.
- Pour rejouer totalement la collecte : `python -m app sync --no-check-for-updates` (la reprise partielle est désactivée).
- Pour purger proprement la base : arrêter le service, dropper les tables/postgres si nécessaire, relancer `init-db`.

## Supervision
- Surveiller :
  - Le quota API (réponses 429/503) dans `logs/app.log`.
  - La taille des tables (index sur `siret`, `code_postal`).
  - Le contenu des alertes (`alerts` + fichier) pour éviter les doublons.
- Contrôler la synthèse e-mail quotidienne (objet `[scope] Synthese run <YYYY-MM-DD HH:MM>`) pour repérer rapidement les écarts : le corps liste les top 10 nouveaux établissements, mises à jour marquantes et correspondances Google tardives.
- Vérifier les erreurs front (console navigateur) en cas de problème CORS ; ajuster `API__ALLOWED_ORIGINS` le cas échéant.
- TODO futur : brancher un système d’alerting externe (Prometheus/Grafana, Sentry, etc.).

## Monitoring quotidien

- L’onglet "Monitoring quotidien" du front interroge `GET /admin/stats/dashboard` toutes les 60 s (toutes les secondes si un run est actif).
- Les graphiques montrent :
  - Nouveaux établissements par jour (BarChart) – permet de valider l’évolution vs `created_records`.
  - Appels API par jour avec le nombre de runs associés (footnote "N runs").
- Les cartes synthétisent :
  - Dernier run (nouveaux établissements, appels API, alertes envoyées, timestamp de démarrage).
  - Répartition Google du dernier run (`found`, `not_found`, `insufficient`, `pending`, `other`).
  - Répartition Google globale (toutes les lignes `establishments`).
  - Statuts administratifs (`etat_administratif`).
- La liste "Alertes quotidiennes" affiche les 10 derniers jours (total vs envoyés) pour vérifier la délivrabilité SMTP.
- Pour investiguer un chiffre anormal :
  1. Ouvrir `sync_runs` (tableau "Historique") pour identifier le run concerné (statut, compteurs).
  2. Contrôler les logs structurés (`sync.run.*`, `sync.collection.*`, `sync.google.summary`).
  3. Recouper avec `alerts` (`SELECT count(*) FROM alerts WHERE run_id = ...`) si nécessaire.

## Observabilité Elastic/Kibana
- Démarrer la pile avec `docker compose up -d biz-tracker-elasticsearch biz-tracker-kibana` (ports 9200 et 5601).
- Activer la journalisation vers Elasticsearch via `.env` (`LOGGING__ELASTICSEARCH__ENABLED=true`, hôte, credentials optionnels).
- Un dashboard prêt à l’emploi est versionné dans `docs/kibana/dashboards.ndjson` (importer via Stack Management > Saved Objects > Import).
- Les événements structurés disponibles : `sync.run.*`, `sync.new_establishment`, `sync.google.summary`, `sync.google.match`, `sync.alert.created`, `alerts.email.sent`, `alerts.email.skipped`, `scheduler.*`, `email.test_sent`.
