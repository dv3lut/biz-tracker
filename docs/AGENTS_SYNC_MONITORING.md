# Synchronisation : deep dive & monitoring

Ce document sert à 2 choses :

1. **Comprendre la synchro** (Sirene → DB → Google → alertes) avec ses modes.
2. **Diagnostiquer vite** dans Kibana : “pourquoi pas d’alertes ?”, “pourquoi beaucoup d’alertes ?”, “où ça a déraillé ?”.

> Source de vérité technique : `app/services/sync/*`, `app/services/google_business/*`, `app/services/alert_service.py`.

## Schéma (vue pipeline)

```mermaid
flowchart TD
  Trigger[Trigger: API / CLI / Scheduler] --> Prepare[Prepare SyncRun + SyncState]
  Prepare --> Collect[Collect Sirene pages]
  Collect --> Persist[Upsert DB + compteurs + checkpoints]
  Persist --> DecideGoogle{Google activé
(mode + API key)}
  DecideGoogle -- non --> Finish[Finish run + summary]
  DecideGoogle -- oui --> Enrich[Google enrichment
(queue + backlog)]
  Enrich --> Alerts[Créer alertes + e-mails clients]
  Alerts --> Summary[Résumé admin]
  Summary --> Finish
```

## Modes de sync (ce que ça change)

- `full` : Sirene + Google + alertes.
- `sirene_only` : Sirene uniquement (Google sauté → pas d’alertes Google).
- `google_pending` : Google uniquement sur les établissements jamais vérifiés.
- `google_refresh` : purge des données Google + relance totale (plutôt diagnostic / recalcul).
- `day_replay` : rejeu d’une date précise (sans perturber l’état global), option de forcer Google.

Référence : `app/services/sync/mode.py` et options CLI dans `app/cli.py`.

## Événements observabilité : “timeline” minimale par run

Pour reconstituer ce qui s’est passé sans se noyer :

- `sync.run.started` / `sync.run.completed` / `sync.run.failed`
- `sync.collection.started` / `sync.page.processed` / `sync.collection.completed`
- `sync.google.summary` (si Google activé)
- `sync.google.enrichment.started` / `sync.google.enrichment.completed` (durées Google)
- `sync.alerts.dispatch.*` (durée création alertes)
- `alerts.email.*` (e-mails clients)
- `sync.summary.email.*` (e-mail admin)

Astuce : **filtrer par `run_id`**.

## Comment lire la pipeline (étape par étape)

### 1) Déclenchement

- API : `POST /admin/sync` crée un run et le lance en tâche de fond.
- Scheduler : `SyncScheduler` peut créer/lancer un run (si pas `local`).
- CLI : `python -m app sync`.

À surveiller :
- `scheduler.*` pour comprendre pourquoi un run a été (ou non) déclenché.
- `sync.run.request_*` côté API (accepté / rejeté / no updates).

### 2) Préparation du run

- Création/chargement `SyncRun` + `SyncState`.
- Calcul de checksum de requête Sirene : si elle change, le curseur est reset.

Événements :
- `sync.run.prepared`
- `sync.cursor.reset` (raison `query_changed`, etc.)

### 3) Collecte Sirene (pagination curseur)

- `sync.collection.started` décrit la fenêtre : `since_creation` ou `creation_range`, `months_back`, `page_size`, `initial_cursor`.
- `sync.page.processed` est le “tick” unitaire (durée page + curseurs + compteurs).
- `sync.new_establishment` / `sync.updated_establishment` existent (très verbeux, utile au debug ciblé).

Événements :
- `sync.collection.started`
- `sync.page.processed`
- `sync.collection.completed`

### 4) Enrichissement Google

- Si `GOOGLE__API_KEY` est absent, l’enrichissement est inactif même en mode `full`.
- Sinon : constitution d’une file (nouvelles créations + backlog selon le mode), puis lookup Places.

Événements :
- `sync.google.summary` : chiffres consolidés (queue/eligible/matched/pending/api calls).
- `sync.google.enrichment.started` / `sync.google.enrichment.completed` : durée et compteurs.
- Niveau lookup (ultra détaillé) :
  - `sync.google.lookup.skipped` (insufficient_query)
  - `sync.google.find_place.query`
  - `sync.google.find_place.candidate_scored`
  - `sync.google.place_details.error`
  - `sync.google.category.evaluated`
  - `sync.google.lookup.result` (`found`, `not_found`, `type_mismatch`, etc.)

### 5) Alertes & e-mails

- Les alertes sont créées à partir des matchs Google et filtrées par clients (subscriptions + `listing_statuses`).

Événements :
- `sync.alerts.dispatch.started` / `sync.alerts.dispatch.completed`
- `sync.alerts.created` + `sync.alert.created` (payload)
- `alerts.email.sent` / `alerts.email.skipped` / `alerts.email.error`
- Admin : `sync.summary.email.sent` / `sync.summary.email.skipped` / `sync.summary.email.error`

## Kibana : requêtes KQL prêtes à l’emploi

### A) Ouvrir la timeline d’un run

1) Trouver le run_id :

- `event.name:"sync.run.completed"` (ou `sync.run.failed`) puis ouvre le champ `run_id`.

2) Timeline minimaliste :

- `run_id:"<UUID>" and event.name:("sync.run.started" or "sync.collection.started" or "sync.collection.completed" or "sync.google.summary" or "sync.google.enrichment.completed" or "sync.alerts.dispatch.completed" or "sync.run.completed" or "sync.run.failed")`

### B) “Pourquoi je n’ai pas d’alertes depuis X jours ?”

- Vérifier si les runs sont déclenchés :
  - `event.name:("sync.run.started" or "sync.run.completed" or "sync.run.failed" or "scheduler.run_scheduled" or "scheduler.skip")`

- Vérifier si Sirene remonte des créations :
  - `event.name:"sync.collection.completed" and created_records:0`

- Vérifier si Google matche :
  - `event.name:"sync.google.summary" and matched_count:0`

- Vérifier si les e-mails sont envoyés/skip :
  - `event.name:("alerts.email.sent" or "alerts.email.skipped" or "alerts.email.error")`

### C) “Pourquoi beaucoup d’alertes d’un coup ?”

- Run concerné (tri par dernier complet) :
  - `event.name:"sync.run.completed"`

- Indices de backlog Google :
  - `event.name:"sync.google.summary" and include_backlog:true`
  - `event.name:"sync.collection.completed" and google_late_matched_count > 0`

- Cas `day_replay` :
  - `event.name:"sync.run.completed" and mode:"day_replay"`

### D) “Les catégories ne matchent plus”

- Focus sur mismatch :
  - `event.name:"sync.google.lookup.result" and status:"type_mismatch"`

- Détail décision catégorie :
  - `event.name:"sync.google.category.evaluated" and category.matched:false`

### E) “Google est en panne / quota”

- Erreurs Places :
  - `event.name:("sync.google.find_place.error" or "sync.google.place_details.error")`

- Surconsommation :
  - `event.name:"sync.google.enrichment.completed"` puis grapher `api_call_count`.

## Recos simples pour simplifier le monitoring (sans tout refaire)

- Utiliser la **timeline minimale** ci-dessus comme réflexe (évite le bruit des événements “par établissement”).
- Ajouter un dashboard “Funnel run” basé sur :
  - `sync.collection.completed` (fetched/created/updated/api calls)
  - `sync.google.summary` (eligible/matched/pending/api calls)
  - `sync.alerts.dispatch.completed` (alerts_created)
  - `alerts.email.sent` (compter par run_id)

---

Si tu veux, je peux aussi préparer un `docs/kibana/` minimal (saved searches + un dashboard JSON) basé sur ces événements (sans changer l’UX de l’app).