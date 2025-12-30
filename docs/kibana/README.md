# Kibana Observability

Ce dossier contient les ressources nécessaires pour superviser Business tracker via l'Elastic Stack.

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

## Déploiement serveur (recommandé)

Un `docker compose` complet (API + Postgres + Elastic + Kibana) est fourni dans `docker-compose.server.yml`.

Note: les scripts d'initialisation Elastic (certificats transport, création des rôles/utilisateurs) sont externalisés dans `scripts/elastic/` pour éviter les pièges d'interpolation Docker Compose et garder un fichier compose lisible.

### Accès Kibana : reverse-proxy vs accès privé

Il y a 2 manières "classiques" de ne pas exposer Kibana en clair :

1) **Via reverse-proxy (HTTPS) + authentification Kibana**

- **Kibana n'est pas exposé via `ports:`**, mais il reste **accessible publiquement** sur `https://kibana.…` car ton reverse-proxy (nginx-proxy) publie le port 443 et route vers Kibana.
- C'est le mode recommandé si tu veux un accès simple depuis n'importe où, avec login.
- Prérequis : tu as déjà un reverse-proxy de type jwilder/nginx-proxy qui tourne sur le serveur (réseau Docker externe `nginx-proxy`).
- Dans ce mode, configure : `KIBANA_VIRTUAL_HOST`, `LETSENCRYPT_EMAIL`, et `KIBANA_PUBLIC_BASE_URL`.

2) **Accès privé (non joignable depuis Internet) via tunnel SSH**

- Dans ce mode, Kibana **n'a pas de `VIRTUAL_HOST`** et **n'a pas de port exposé publiquement**.
- Option la plus simple : exposer Kibana uniquement en local serveur :
   - ajouter `ports: ["127.0.0.1:5601:5601"]` au service Kibana
   - supprimer les variables `VIRTUAL_HOST` / `LETSENCRYPT_*` du service Kibana
- Ensuite, depuis ton poste :
   - `ssh -L 5601:localhost:5601 <user>@<ton-serveur>`
   - ouvrir `http://localhost:5601` dans ton navigateur

Le reverse-proxy sert donc à publier un domaine HTTPS et à router le trafic vers le bon container. Si tu ne veux pas que Kibana soit accessible publiquement du tout, n'utilise pas le reverse-proxy pour Kibana et passe par un tunnel SSH.

### Restreindre par IP (kibana + admin)

Si tu veux que l'URL existe mais qu'elle ne soit accessible qu'à certaines IP (ex: ta box, ton VPN, tes bureaux), tu peux mettre en place une **allowlist IP** au niveau de `nginx-proxy`.

- Crée un fichier `vhost.d/<hostname>` côté nginx-proxy avec `allow ...; deny all;`.
- Fais la même chose pour `kibana.business-tracker.fr` ET `admin.business-tracker.fr`.

Un exemple est fourni dans `docs/nginx-proxy/vhost.d/` et la procédure dans `docs/nginx-proxy/README.md`.

### 1) Corriger le "Kibana server not ready"

La cause la plus fréquente est une URL Elasticsearch incorrecte.

- Depuis le container Kibana, l'hôte doit être le nom du service Docker (ex: `http://biztracker-elasticsearch:9200`).
- Un hôte de type `business-tracker.elasticsearch:9200` ne fonctionnera pas sauf si tu as explicitement configuré ce DNS/alias dans tes réseaux Docker.

### 2) Protéger l'accès (authentification)

Pour éviter que Kibana soit accessible publiquement sans login, active la sécurité Elastic (xpack) et connecte Kibana avec l'utilisateur `kibana_system`.

Un exemple prêt à copier est fourni dans `docs/kibana/docker-compose.secure.yml`.

Variables minimales à définir dans ton `.env` serveur :

- `ELASTIC_PASSWORD` (mot de passe admin Elasticsearch)
- `KIBANA_SYSTEM_PASSWORD` (mot de passe de l'utilisateur `kibana_system`)
- `ELASTIC_TRANSPORT_SSL_TRUSTSTORE_PASSWORD` (>= 6 caractères, défaut: `changeit`) pour le truststore PKCS12 utilisé par le TLS transport
- `KIBANA_PUBLIC_BASE_URL` (ex: `https://kibana.business-tracker.fr`) pour supprimer le warning "public URL" et activer correctement les fonctionnalités qui génèrent des liens
- `KIBANA_SECURITY_ENCRYPTION_KEY`, `KIBANA_ENCRYPTED_SAVED_OBJECTS_KEY`, `KIBANA_REPORTING_ENCRYPTION_KEY` (chaînes longues et stables)

Recommandations réseau :

- Ne pas exposer Elasticsearch (9200) à Internet. En prod, évite `ports: - "9200:9200"` ou bind sur `127.0.0.1:9200:9200` si tu en as besoin localement.
- Exposer Kibana uniquement via le reverse proxy TLS (nginx-proxy) et pas directement via un port public.

## Import des tableaux de bord

1. Ouvrir Kibana (`http://localhost:5601`) > Management > **Stack Management** > **Saved Objects** > **Import**.
2. Sélectionner le fichier `docs/kibana/dashboards.ndjson` et cocher l’option « Replace index patterns with matching ones » si demandée.
3. Après import, un data view `biz-tracker-observability-*` et les dashboards **"Business tracker - Synchronisation"** et **"Business tracker - Chronologie run"** sont disponibles.

## Contenu du dashboard

- **Runs terminés** : liste des synchronisations réussies avec la durée, le nombre de nouveaux établissements et les compteurs Google (file totale, éligibles, fiches trouvées, restant à traiter).
- **Résumé Google Places** : synthèse par run des tentatives d’enrichissement (volume total traité, éligibles, correspondances et backlog restant).
- **Nouveaux établissements** : vue détaillée par établissement (SIRET, nom, localisation, URL Google éventuelle).
- **Alertes** : journal des alertes Google My Business envoyées.
- **Runs en échec** : chronologie des incidents avec le type et le message d’erreur associé.
- **Appels externes** : trois tables (tous services, Sirene, Google Places) pour suivre les statuts HTTP, durées et rejets côté APIs partenaires.
- **Chronologie run** : table ordonnée par timestamp (ASC) pour rejouer toutes les étapes d'un run. Utiliser la barre de filtre avec `run_id: <uuid>` pour cibler un run précis.

Les vues sont basées sur les événements structurés émis par le backend (`event.name`). Vous pouvez créer des filtres ou des visualisations Lens supplémentaires à partir du même data view pour explorer des KPI spécifiques (volume par jour, délais moyens, etc.).

## Export / duplication

Le fichier `dashboards.ndjson` peut être versionné tel quel ou ré-exporté depuis Kibana après personnalisation : Stack Management > Saved Objects > Export.
