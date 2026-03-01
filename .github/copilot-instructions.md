# GitHub Copilot — Instructions (monorepo)

Objectif : éviter de ré-implémenter des logiques déjà présentes et garder la cohérence entre back/front.

## Avant toute modification

1) Lire l’index : `AGENTS.md` (racine).
2) Si tu touches le backend : lire `biz-tracker-back/docs/AGENTS.md` puis, selon le sujet :
   - `biz-tracker-back/docs/AGENTS_CODEMAP.md` (où chercher quoi)
   - `biz-tracker-back/docs/AGENTS_SYNC_MONITORING.md` (pipeline sync + monitoring)
   - `biz-tracker-back/docs/AGENTS_TECH.md` / `AGENTS_OPERATIONS.md`
3) Si tu touches les contrats HTTP : garder le front synchronisé.

## Règles de base

- Ne pas ajouter de nouvelles features non demandées.
- Privilégier des changements petits, ciblés et testés (backend : `cd biz-tracker-back && .venv/bin/python -m pytest -W error`).
- Pour la sync : conserver les événements `log_event(...)` et inclure `run_id`/`scope_key` quand pertinent.

## Code style :
Fichiers par trop grands, pas plus de 300 lignes sans raison.
