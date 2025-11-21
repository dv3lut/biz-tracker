# Contexte fonctionnel

- **Objectif** : détecter la création de nouveaux établissements de restauration en France (NAF 56.10A) grâce à l’API Sirene officielle.
- **Cible** : établissements actifs (`etatAdministratifEtablissement = A`) ; les SIRET sont utilisés comme identifiant principal.
- **Workflow** :
  1. Synchronisation complète initiale (collecte de tout l’historique pertinent).
  2. Exécutions incrémentales quotidiennes après la mise à jour Sirene (`service informations`) en rejouant `dateCreationEtablissement` autour du checkpoint `last_creation_date`.
  3. Détection des nouveaux SIRET pour alertes internes (mail + logs).
  4. Supervision et pilotage via une API admin sécurisée et un front React dédié (`biz-tracker-admin-ui`).
  5. Restitution quotidienne des indicateurs clés (nouveaux établissements, appels API, alertes, statuts Google) via le tableau de bord `/admin/stats/dashboard`.
- **Contraintes clés** :
  - Respect du quota (30 appels/minute) et du paramètre `curseur` pour paginer de manière stable.
  - Capacité à reprendre un run interrompu (stockage des curseurs + métadonnées de run).
  - Stockage minimaliste mais suffisant : nom + fallbacks, adresse complète, dates clés, NAF, état administratif.
  - Accès API limité par jeton administrateur configurable (`X-Admin-Token`).
- **Monitoring quotidien** : les agrégations sont calculées depuis `sync_runs`, `establishments` et `alerts` (dernière synchro, séries journalières sur 30 jours, répartition des statuts). Le front affiche graphiques, répartitions Google (global & dernier run) et alertes envoyées.
- Les run récents distinguent désormais les correspondances Google immédiates (créations du jour) des rattrapages ultérieurs, et comptent les établissements déjà présents mais modifiés.
- Une synthèse e-mail (statistiques + top 10) est diffusée aux destinataires renseignés dans `admin_recipients` après chaque run réussi lorsque SMTP est opérationnel.
- **Prochaines évolutions envisagées** : enrichir les alertes (cartographie, scoring), exposer un dashboard public ou des intégrations externes, compléter le monitoring (SLA, volumétrie API Google).
