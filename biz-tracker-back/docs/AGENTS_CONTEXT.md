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
- **Segmentation géographique** : le filtrage et l’affectation clients s’appuient sur les **départements**. La sélection par région côté UI correspond à l’ensemble de ses départements, et les codes Corse (`2A`, `2B`) sont harmonisés avec l’alias `20`.
- **Prochaines évolutions envisagées** : enrichir les alertes (cartographie, scoring), exposer un dashboard public ou des intégrations externes, compléter le monitoring (SLA, volumétrie API Google).

## Statuts d'ancienneté des fiches Google

- `recent_creation` : la date d'origine de la fiche (ou, à défaut, l'absence totale d'avis Google) suggère une création concomitante avec l'établissement Sirene. On considère également comme « récents » les listings dont `user_ratings_total` vaut 0 ou pour lesquels l'API retourne explicitement une liste d'avis vide.
- `recent_creation_missing_contact` : cas particuliers des fiches récentes pour lesquelles aucun canal de contact exploitable n'a été identifié (pas de numéro de téléphone, pas d'URL). Elles restent prioritaires côté prospection mais nécessitent un traitement dédié.
- `not_recent_creation` : la fiche Google présente des signaux d'ancienneté (avis plus anciens que 2 semaines, volume d'avis significatif, date d'origine bien antérieure) et correspond à une création ancienne par rapport au SIRET recensé.
- `unknown` : impossible d'établir l'âge relatif (Google ne retourne ni périodes d'ouverture ni avis exploitables **et** nous ne disposons pas d'une date de création Sirene fiable). Dans ce cas aucun signal n'est affiché aux utilisateurs.

Les équipes peuvent désormais sélectionner explicitement les statuts à inclure :

- Chaque client possède un champ `listing_statuses` (JSONB) qui détermine les alertes et exports auxquels il a accès. Les valeurs sont limitées aux trois statuts filtrables (`recent_creation`, `recent_creation_missing_contact`, `not_recent_creation`).
- La modale d'export Google propose les mêmes cases à cocher. L'API refuse les requêtes qui n'incluent aucun statut, ce qui garantit un échantillon cohérent entre exports, alertes et e-mails.
- Les statuts `unknown` restent pris en compte dans les agrégats (dashboard, monitoring) mais ne sont pas exportables tant qu'un signal exploitable n'a pas été identifié.
