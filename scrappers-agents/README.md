# scrappers-agents

Scripts d'automation Selenium packagés en images Docker, déployés sur le VPS de la même façon que `biz-tracker-back` / `biz-tracker-admin`.

Sous-dossiers :
- [`annuaires-comptables/`](annuaires-comptables/) — daemon de contact via l'annuaire OEC.

---

## ⚠️ Compatibilité avec la stack Docker existante

Aucun risque d'interférence avec les containers actuels :
- Container isolé, sur le réseau Docker par défaut (pas attaché à `nginx-proxy` ni à `internal`).
- N'expose aucun port, ne touche à aucun volume Docker existant.
- N'utilise ni Postgres, ni Elasticsearch, ni l'API back. Seul flux sortant : SMTP Mailjet.
- Chromium headless ≈ 200–400 Mo RAM par container — vérifie la marge dispo sur le VPS.

---

## 1. Préparation du VPS (à faire une seule fois)

Docker et docker-compose sont déjà installés (cf. `biz-tracker-back`). Il reste à créer le dossier de déploiement et le `.env`.

### a) Créer le dossier et le `.env`

```bash
ssh dorian@<VPS>
mkdir -p ~/scrappers-agents/annuaires-comptables/data
cd ~/scrappers-agents/annuaires-comptables
nano .env
```

Colle (et adapte) :

```env
EMAIL__SMTP_HOST=in-v3.mailjet.com
EMAIL__SMTP_PORT=587
EMAIL__SMTP_USERNAME=<copie depuis biz-tracker-back/.env.prod>
EMAIL__SMTP_PASSWORD=<copie depuis biz-tracker-back/.env.prod>
EMAIL__USE_TLS=true
EMAIL__FROM_ADDRESS=notification@business-tracker.fr

CABINETS_PER_DAY=100
TZ=Europe/Paris
```

```bash
chmod 600 .env
```

### b) Premier déploiement

Déclenche le workflow [`scrappers-deploy.yml`](../.github/workflows/scrappers-deploy.yml) :
- depuis l'onglet **Actions** de GitHub → "Deploy scrappers-agents/annuaires-comptables to VPS" → **Run workflow**, OU
- en poussant un tag : `git tag annuaires-comptables/v0.1.0 && git push --tags`.

Le workflow :
1. Build l'image Docker (Python 3.11 + Chromium + chromedriver + script).
2. La pousse sur Docker Hub (`dv3lut/annuaires-comptables:latest`).
3. SCP `docker-compose.server.yml` vers le VPS.
4. SSH → `docker-compose pull && up -d`.

Au tout premier `up`, l'entrypoint copie le CSV bundlé dans l'image vers `~/scrappers-agents/annuaires-comptables/data/cabinets_oec.csv`. **Ensuite ce fichier n'est plus jamais écrasé** : c'est lui qui contient l'état "déjà contacté".

---

## 2. Persistence du CSV — comment ça marche

```
VPS:
  ~/scrappers-agents/annuaires-comptables/
    ├── docker-compose.server.yml
    ├── .env
    └── data/
        └── cabinets_oec.csv     ← persistent (bind-mount)

Container annuaires-comptables:
  /data/cabinets_oec.csv         ← monté depuis le host
```

Le script écrit dans le CSV après **chaque** envoi. Si le container crashe, redémarre, ou est recréé pour mettre à jour l'image, l'état est intact car il est sur le host (pas dans la couche containerisée).

Reset complet de l'état (re-contacter tout le monde) :

```bash
cd ~/scrappers-agents/annuaires-comptables/data
# vide la dernière colonne `contacted` du CSV (ou supprime le fichier pour repartir
# du CSV bundlé dans l'image)
rm cabinets_oec.csv
docker-compose -f ../docker-compose.server.yml restart
```

---

## 3. Commandes utiles au quotidien

| Action | Commande (depuis `~/scrappers-agents/annuaires-comptables`) |
|---|---|
| Statut | `docker-compose -f docker-compose.server.yml ps` |
| Logs en direct | `docker-compose -f docker-compose.server.yml logs -f` |
| Stopper | `docker-compose -f docker-compose.server.yml stop` |
| Redémarrer | `docker-compose -f docker-compose.server.yml restart` |
| Mettre à jour l'image | `docker-compose -f docker-compose.server.yml pull && docker-compose -f docker-compose.server.yml up -d` |
| Changer le N quotidien | éditer `CABINETS_PER_DAY` dans `.env` puis `restart` |
| Voir l'état du CSV | `awk -F';' 'NR>1 {print $NF}' data/cabinets_oec.csv \| sort \| uniq -c` |
| Shell dans le container | `docker exec -it annuaires-comptables sh` |

Tu peux te déconnecter du SSH (`exit`), le container continue de tourner (`restart: unless-stopped`).

---

## 4. Comportement du daemon

À chaque tour :
1. Calcule un horaire aléatoire dans `[09:30, 12:30]` (heure locale, fixée par `TZ` dans le compose).
2. Dort jusqu'à cette heure.
3. Lance Chromium headless dans le container, traite N sites en réutilisant la même session.
4. Met à jour `/data/cabinets_oec.csv` (colonne `contacted` = `1` ou `err:<raison>`) après chaque envoi.
5. Envoie un récap email à `dorian110620@gmail.com` via Mailjet.
6. Boucle pour le lendemain.

---

## 5. Dev local (Mac)

### Option A — sans Docker (rapide pour debug avec navigateur visible)

```bash
cd scrappers-agents/annuaires-comptables
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python contact_expert_comptable.py 5
```

Le browser sera **visible**. SMTP lu depuis `../../biz-tracker-back/.env.prod` automatiquement.

### Option B — Docker local

```bash
cd scrappers-agents/annuaires-comptables
cp .env.example .env   # remplis les credentials Mailjet
docker build -t annuaires-comptables:local .
docker run --rm -it \
  --env-file .env \
  -v "$PWD/data:/data" \
  annuaires-comptables:local \
  python contact_expert_comptable.py 5
```

---

## 6. Secrets GitHub requis (déjà en place pour les autres workflows)

`SSH_HOST`, `SSH_USER`, `SSH_KEY`, `SSH_PORT`, `SSH_PASSPHRASE`, `DOCKER_HUB_USERNAME`, `DOCKER_HUB_ACCESS_TOKEN`.
