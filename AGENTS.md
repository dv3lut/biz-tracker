# Agents Hub (Monorepo)

Ce depot regroupe les deux projets Business tracker et les ressources utiles pour les prochaines iterations assistees par Copilot.

## Règle d’or — Tests systématiques

Après **toute modification de code**, exécuter les tests adaptés au périmètre avant de clôturer la tâche.
- Backend : `cd biz-tracker-back && .venv/bin/python -m pytest -W error` (couverture incluse).
- Front : `source ~/.nvm/nvm.sh && npm run build` (inclut `tsc`).
- Landing : `source ~/.nvm/nvm.sh && npm run build`.

## Discipline de correction de bug

Quand un bug est remonté, appliquer systématiquement la séquence suivante :
1. **Écrire un test** qui reproduit le bug (dans la mesure du possible).
2. **Corriger le code** pour faire passer le test.
3. **Relancer les tests** et vérifier qu’ils sont verts.
4. **Reporter** explicitement ces étapes dans le compte rendu de la tâche.

- `biz-tracker-back/` : backend FastAPI + Typer. La documentation detaillee pour les agents se trouve dans `biz-tracker-back/docs/AGENTS_CONTEXT.md`, `AGENTS_TECH.md` et `AGENTS_OPERATIONS.md`.
- `biz-tracker-front/` : interface React de pilotage. Elle consomme l'API admin exposee par le backend et s'aligne sur son schema HTTP.
- `biz-tracker-landing-page/` : landing page marketing (Vite + React). Le formulaire appelle l'API publique du backend et declenche l'envoi d'un email vers `contact@business-tracker.fr`.
- `docs/postman_collection.json` (backend) : reference commune pour les appels API. Le front doit rester synchronise avec cette definition (variables `baseUrl`, entete `X-Admin-Token`).

## Cartographie rapide des fichiers utiles

### Backend (`biz-tracker-back/`)

| Zone | Fichiers / responsabilité |
| --- | --- |
| API admin | `app/api/routers/*_router.py` expose chaque ressource (`sync`, `stats`, `alerts`, `google`, `email`). `dependencies.py` gère les sessions SQLA et le token admin. |
| Clients externes | `app/clients/sirene_client.py` pilote Sirene, `google_places_client.py` encapsule Places API + retries. |
| Services métier | `app/services/sync_service.py` orchestre les runs Sirene, `sync_scheduler.py`/`incremental_scheduler.py` déclenchent les runs automatiques, `alerts/alert_service.py` et `email_service.py` gèrent les notifications, `google_business/google_business_service.py` + `google_business/google_lookup_engine.py` traitent l’enrichissement Google. |
| Rates & retries | `app/services/rate_limiter.py` + `google/google_retry_config.py` contrôlent les quotas API Google. |
| Données | `app/db/models.py` définit le schéma, `session.py` fournit les connexions, `migrations.py` contient les helpers d’initialisation. |
| Mapping & utils | `app/services/establishment_mapper.py` nettoie les payloads Sirene, `app/utils/*.py` héberge les fonctions transverses (dates, URLs, hashing, Google listing). |
| Tests | `tests/test_*.py` couvrent Google (`test_google_business_service.py`), alertes, scheduler et API admin. |
| Scripts & SQL | `scripts/deploy.sh`, `scripts/extract_pdf_text.py` et `sql/restore.sh`/`sql/backups` pour l’exploitation.

### Frontend (`biz-tracker-front/`)

| Zone | Fichiers / responsabilité |
| --- | --- |
| Entrée & routing | `src/main.tsx` monte l’app, `src/App.tsx` structure les sections (dashboard, clients, alertes). |
| API client | `src/api/*.ts` regroupe les appels (`sync.ts`, `alerts.ts`, `google.ts`, `clients.ts`, `stats.ts`, etc.) via `api/http.ts`. |
| Types & constantes | `src/types.ts`, `src/constants/*` décrivent les schémas admin, choix de statuts Google et paramètres UI. |
| Hooks | `src/hooks/useAdminToken.ts`, `useDashboard.ts`, etc. centralisent les effets React Query et la gestion du token admin. |
| Composants principaux | `src/components/DashboardInsights.tsx`, `ClientsSection.tsx`, `AlertsList.tsx`, `AdminEmailConfigSection.tsx`, `GoogleExportModal.tsx`, `ClientModal.tsx` pilotent les pages métier. |
| Visualisations | `src/components/BarChart.tsx` et `DashboardInsights.tsx` affichent les séries `stats/dashboard`. |
| Styles & build | `src/styles/index.css` (styles split), `vite.config.ts`, `tsconfig*.json` et `package.json` définissent le thème, les alias et les scripts (`npm run dev`, `npm start`). |

### Landing page (`biz-tracker-landing-page/`)

| Zone | Fichiers / responsabilité |
| --- | --- |
| Page d'accueil | `src/pages/Index.tsx` assemble les sections et inclut le formulaire. |
| Formulaire | `src/components/ContactForm.tsx` POST sur `${VITE_APP_API_BASE_URL}/public/contact`. |
| Config Vite | `vite.config.ts` (port de dev, aliases). |
| Docs agent | `biz-tracker-landing-page/AGENTS.md` détaille l'architecture et le flux email. |

> Astuce : lorsque tu dois intervenir sur une fonctionnalité, commence par ce tableau puis déroule les sections détaillées des fichiers `biz-tracker-back/docs/AGENTS_*.md` pour trouver le module précis.

## Demarrage rapide

1. Backend : consulter `biz-tracker-back/README.md`, creer `.env`, lancer `docker compose up -d db`, puis `python -m app serve` (config `Backend: FastAPI serve` dans `.vscode/launch.json`).
2. Front : consulter `biz-tracker-front/README.md`, creer `.env`, executer `npm run dev` depuis le dossier front.
3. Postman : importer `biz-tracker-back/docs/postman_collection.json` pour explorer et valider les endpoints admin.

## Bases solides pour les prochaines missions

- Maintenir a jour les fichiers `AGENTS_*.md` du backend et completer cette page si de nouvelles briques communes sont ajoutees.
- Garder la collection Postman comme source de verite des contrats HTTP et synchroniser le front en consequence.
- Documenter toute nouvelle commande Typer ou flux back-office dans les READMEs correspondants.
- Verifier que la configuration `.vscode/launch.json` suffit pour lancer l'API localement a chaque evolution d'environnement.
- Noter les pre-requis (versions Python/Node, variables d'environnement critiques) des deux projets pour alleger les prochains onboardings.
- Clore chaque itération en executant les tests automatises avec couverture : `cd biz-tracker-back && .venv/bin/python -m pytest -W error`. Le fichier `pytest.ini` force `--cov=app --cov-config=.coveragerc`, donc verifier que le seuil 95 % reste depasse avant de considerer une tache comme terminee.
- Consulter rapidement la documentation Sirene locale via `python scripts/extract_pdf_text.py "sirene-doc/<fichier>.pdf"` depuis `biz-tracker-back/`.
- En cas de purge de donnees, utiliser l'endpoint `DELETE /admin/sync-runs/{run_id}` qui supprime les etablissements crees par un run, ses alertes et reinitialise l'etat de synchro.

### Discipline de refactor (anti code mort)

- Après une refonte, supprimer dans la même itération les anciens chemins de code, variables d'environnement, docs, et artefacts Kibana devenus obsolètes.
- Vérifier par recherche globale que les anciens noms/clefs n'existent plus, et maintenir les contrats HTTP + dashboards synchronisés.

Ces informations forment le socle attendu avant d'entamer une nouvelle iteration accompagnee.
