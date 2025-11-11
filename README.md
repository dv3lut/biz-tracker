# Biz Tracker Admin UI

Interface d'administration React pour piloter l'API Biz Tracker. Le projet peut vivre hors du dépôt backend (ex. dossier frère `../biz-tracker-admin-ui`).

## Prérequis

- Node.js 18 ou version supérieure
- npm 9 ou version supérieure

## Démarrage

```bash
npm install
cp .env.example .env  # Adapter l'URL de l'API si nécessaire
npm run dev
```

L'application est servie sur [http://localhost:5173](http://localhost:5173). La valeur par défaut de `VITE_API_BASE_URL` pointe sur `http://localhost:8000`.

### Autorisations CORS côté backend

Assurez-vous que la variable `API__ALLOWED_ORIGINS` du backend contient l'origine utilisée (`http://localhost:5173` par défaut). Exemple dans `.env` du backend :

```bash
API__ALLOWED_ORIGINS=["http://localhost:5173"]
```

## Build de production

```bash
npm run build
npm run preview
```

## Fonctionnalités

- Synthèse des métriques principales (`/admin/stats/summary`).
- Historique des synchronisations et suivi des ETA (`/admin/sync-runs`).
- Etat des curseurs et checkpoints (`/admin/sync-state`).
- Liste des alertes récentes (`/admin/alerts/recent`).
- Déclenchement de la synchronisation unifiée (`/admin/sync`).
- Envoi d'un e-mail de test pour valider la configuration SMTP (`/admin/email/test`).
