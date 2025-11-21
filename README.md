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

L'application est servie sur [http://localhost:5173](http://localhost:5173). La valeur par défaut de `VITE_APP_API_BASE_URL` pointe sur `http://localhost:8000`.

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
- Pilotage des catégories/sous-catégories NAF et des abonnements clients (`/admin/naf-*`).

## Gestion des catégories NAF et abonnements clients

La vue **Clients** regroupe désormais deux panneaux : la gestion des comptes clients et l'orchestrateur des catégories/sous-catégories NAF. Ce module permet de contrôler précisément quelles alertes sont reçues par chaque client.

1. **Catégories NAF** : utilisez le bouton « Ajouter une catégorie » pour créer un conteneur logique (nom + ordre d'affichage). Chaque carte affiche le nombre d'abonnements actifs et propose l'édition ou la suppression (protégée par confirmation).
2. **Sous-catégories** : ouvrez le bouton « Ajouter une sous-catégorie » (ou l'icône « + » sur une carte) pour définir le code/label NAF, le prix mensuel, l'ordre et l'état actif/inactif. Les sous-catégories sont rattachées à une catégorie et peuvent être désactivées sans suppression définitive.
3. **Abonnements client** : dans le formulaire d'édition de client, la section « Abonnements NAF » liste les sous-catégories actives. Cochez/decochez les souscriptions puis sauvegardez pour que l'API propage la configuration.

> ℹ️ Les appels réseau reposent sur les endpoints `/admin/naf-categories*` et `/admin/naf-sub-categories*` documentés dans la collection Postman backend. Le front applique automatiquement le jeton `X-Admin-Token` renseigné dans l'UI.
