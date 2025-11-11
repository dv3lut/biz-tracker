# Kibana Observability

Ce dossier contient les ressources nécessaires pour superviser Biz Tracker via l’Elastic Stack.

## Pré-requis

1. S’assurer que le backend envoie bien ses logs vers Elasticsearch :
   - activer `LOGGING__ELASTICSEARCH__ENABLED=true` dans `.env`.
   - vérifier l’URL (`LOGGING__ELASTICSEARCH__HOSTS`), le préfixe d’index (`LOGGING__ELASTICSEARCH__INDEX_PREFIX`) et l’environnement (`LOGGING__ELASTICSEARCH__ENVIRONMENT`).
   - relancer l’API/CLI pour recharger la configuration de logging.
2. Démarrer l’infrastructure observabilité :
   ```bash
   docker compose up -d biz-tracker-elasticsearch biz-tracker-kibana
   ```
   Elasticsearch écoute sur `http://localhost:9200`, Kibana sur `http://localhost:5601`.

## Import des tableaux de bord

1. Ouvrir Kibana (`http://localhost:5601`) > Management > **Stack Management** > **Saved Objects** > **Import**.
2. Sélectionner le fichier `docs/kibana/dashboards.ndjson` et cocher l’option « Replace index patterns with matching ones » si demandée.
3. Après import, un data view `biz-tracker-observability-*` et le dashboard **“Biz Tracker - Synchronisation”** sont disponibles.

## Contenu du dashboard

- **Runs terminés** : liste des synchronisations réussies avec la durée, le nombre de nouveaux établissements et les compteurs Google (file totale, éligibles, fiches trouvées, restant à traiter).
- **Résumé Google Places** : synthèse par run des tentatives d’enrichissement (volume total traité, éligibles, correspondances et backlog restant).
- **Nouveaux établissements** : vue détaillée par établissement (SIRET, nom, localisation, URL Google éventuelle).
- **Alertes** : journal des alertes Google My Business envoyées.
- **Runs en échec** : chronologie des incidents avec le type et le message d’erreur associé.
- **Appels externes** : trois tables (tous services, Sirene, Google Places) pour suivre les statuts HTTP, durées et rejets côté APIs partenaires.

Les vues sont basées sur les événements structurés émis par le backend (`event.name`). Vous pouvez créer des filtres ou des visualisations Lens supplémentaires à partir du même data view pour explorer des KPI spécifiques (volume par jour, délais moyens, etc.).

## Export / duplication

Le fichier `dashboards.ndjson` peut être versionné tel quel ou ré-exporté depuis Kibana après personnalisation : Stack Management > Saved Objects > Export.
