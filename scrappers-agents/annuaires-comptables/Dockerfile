# syntax=docker/dockerfile:1
FROM python:3.11-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    CHROME_BIN=/usr/bin/chromium \
    CHROMEDRIVER=/usr/bin/chromedriver \
    CSV_PATH=/data/cabinets_oec.csv \
    HEADLESS=1

WORKDIR /app

# Chromium + chromedriver + libs nécessaires à Selenium headless
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        chromium \
        chromium-driver \
        ca-certificates \
        fonts-liberation \
        libasound2 \
        libatk-bridge2.0-0 \
        libcups2 \
        libdrm2 \
        libgbm1 \
        libnspr4 \
        libnss3 \
        libxcomposite1 \
        libxdamage1 \
        libxfixes3 \
        libxkbcommon0 \
        libxrandr2 \
        xdg-utils \
        tini \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt /app/requirements.txt
RUN pip install --upgrade pip && pip install -r requirements.txt

COPY contact_expert_comptable.py /app/
COPY scrapper-oec.py /app/
COPY docker-entrypoint.sh /app/

# CSV par défaut bundlé dans l'image — l'entrypoint le copie vers /data lors du
# tout premier démarrage si /data/cabinets_oec.csv n'existe pas encore.
COPY cabinets_oec.csv /app/cabinets_oec.csv.default

RUN chmod +x /app/docker-entrypoint.sh

# /data = volume persistant (CSV d'état + logs éventuels)
VOLUME ["/data"]

ENTRYPOINT ["/usr/bin/tini", "--", "/app/docker-entrypoint.sh"]
CMD ["python", "contact_expert_comptable.py", "100"]
