#!/bin/sh
set -e

# Bootstrap du CSV : si /data/cabinets_oec.csv n'existe pas (1er démarrage),
# on y dépose la version bundlée dans l'image. Sur les redémarrages suivants,
# le CSV existant (avec l'état "contacted") est conservé.
mkdir -p /data
if [ ! -f /data/cabinets_oec.csv ]; then
    echo "→ Bootstrap CSV initial dans /data"
    cp /app/cabinets_oec.csv.default /data/cabinets_oec.csv
fi

exec "$@"
