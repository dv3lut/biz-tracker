# Agents — Biz Tracker Frontend

Ce fichier documente les pré-requis, configurations et patterns à respecter lors du développement assisté par Copilot sur le frontend.

## Configuration Node.js et npm

### ⚠️ Problème d'environnement sur cette machine

Sur cette machine, `npm` ne se trouve pas directement dans le `$PATH` du shell standard. **Avant toute commande npm, il faut sourcer le fichier nvm** :

```bash
source ~/.nvm/nvm.sh
```

### Commandes correctes pour développer

- **Démarrer le serveur local** : `source ~/.nvm/nvm.sh && npm run dev`
- **Compiler la production** : `source ~/.nvm/nvm.sh && npm run build`
- **Compiler et vérifier** : `source ~/.nvm/nvm.sh && npm run build` (inclut `tsc` automatiquement)
- **Prévisualiser la production** : `source ~/.nvm/nvm.sh && npm run preview`
- **Installer des packages** : `source ~/.nvm/nvm.sh && npm install <package>`

### Exemple d'intégration avec VS Code

Si vous utilisez un task dans `.vscode/tasks.json` pour lancer la build, assurez-vous que la commande sourçe nvm :

```json
{
  "label": "build frontend",
  "type": "shell",
  "command": "source ~/.nvm/nvm.sh && npm run build",
  "cwd": "${workspaceFolder}/biz-tracker-front"
}
```

## Structure du frontend

Le frontend est organisé selon :

| Zone | Fichiers / Responsabilité |
| --- | --- |
| API client | `src/api/*.ts` regroupe les appels (`sync.ts`, `alerts.ts`, `google.ts`, `clients.ts`, `stats.ts`, etc.). |
| Types & constantes | `src/types.ts`, `src/constants/*` décrivent les schémas et les choix de statuts. |
| Hooks React | `src/hooks/useAdminToken.ts`, `useDashboard.ts`, etc. centralisent les effets React Query. |
| Composants | `src/components/*.tsx` groupent les vues métier (modals, sections, cartes, tableaux). |
| Utilities | `src/utils/sync.ts`, `dates.ts`, etc. exposent des fonctions transverses. |
| Styles | `src/styles.css` définit le thème et les layouts globaux. |
| Build & config | `vite.config.ts`, `tsconfig*.json`, `package.json` pour Vite et TypeScript. |

## Validation et build

### TypeScript

La build exécute `tsc` en premier (défini dans `package.json` : `"tsc && vite build"`) pour vérifier tous les types. En cas d'erreur TS, le build échoue et n'exécute pas Vite.

### Compilations courantes

Après éditer des fichiers React/TS, relancer :

```bash
source ~/.nvm/nvm.sh && npm run build
```

Cela validera la cohérence des types et produira un bundle minifié dans `dist/`.

## Frontend — Backend synchronisation

- La collection Postman (`postman_collection.json`) documente tous les endpoints admin.
- Le front doit rester synchronisé avec les changements d'API : ajouter une prop, une route, ou un schéma de réponse au backend nécessite une mise à jour des `src/api/*.ts` et `src/types.ts`.
- Le token d'admin (`X-Admin-Token`) est requis pour chaque requête ; voir `src/api/http.ts` pour l'injection.

## Notes pour les prochaines itérations

1. **NAF codes** : normalisation frontend (sans point interne) vs affichage formaté (avec point). Voir `src/utils/sync.ts` pour `normalizeNafCode`, `canonicalizeNafCode`, et `denormalizeNafCode`.
2. **Modal SyncModeModal** : les contrôles (radio/checkboxes) sont positionnés à droite du contenu ; vérifier `src/styles.css` (`.mode-option-body`, `.naf-category-header`, etc.) si vous modifiez la structure.
3. **Build/test cycle** : souvenez-vous de sourcer nvm avant npm. Intégrer cela dans les raccourcis ou scripts de développement.
4. **Warnings de Rollup** : les chunks dépassent 500 KiB ; c'est un warning d'optimisation non bloquant pour le moment. Considérer une amélioration du chunking si la taille continue de croître.

---

*Dernière mise à jour : 28 novembre 2025*
