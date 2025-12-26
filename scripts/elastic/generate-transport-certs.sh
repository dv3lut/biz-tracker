#!/usr/bin/env bash
set -euo pipefail

CERTS_DIR="/usr/share/elasticsearch/config/certs"
CA_P12="$CERTS_DIR/elastic-stack-ca.p12"
TRUSTSTORE_P12="$CERTS_DIR/elastic-stack-ca-truststore.p12"
CA_CERT_PEM="$CERTS_DIR/elastic-stack-ca.crt"
NODE_CERT_P12="$CERTS_DIR/elastic-certificates.p12"

mkdir -p "$CERTS_DIR"
echo "CA_PATH=$CA_P12"
echo "TRUSTSTORE_PATH=$TRUSTSTORE_P12"
echo "CA_CERT_PEM=$CA_CERT_PEM"
echo "CERT_PATH=$NODE_CERT_P12"

# keytool exige un mot de passe non vide (>= 6 chars) pour créer un PKCS12
TRUSTSTORE_PASS="${ELASTIC_TRANSPORT_SSL_TRUSTSTORE_PASSWORD:-changeit}"
if [[ ${#TRUSTSTORE_PASS} -lt 6 ]]; then
  echo "ELASTIC_TRANSPORT_SSL_TRUSTSTORE_PASSWORD must be at least 6 characters" >&2
  exit 1
fi

if [[ ! -f "$CA_P12" ]]; then
  echo "Generating transport CA"
  /usr/share/elasticsearch/bin/elasticsearch-certutil ca --silent --out "$CA_P12" --pass ""
else
  echo "Transport CA already exists"
fi

if [[ ! -f "$TRUSTSTORE_P12" ]]; then
  echo "Building CA truststore (trusted cert entry)"

  if ! /usr/share/elasticsearch/jdk/bin/keytool \
    -exportcert \
    -rfc \
    -alias ca \
    -keystore "$CA_P12" \
    -storetype PKCS12 \
    -storepass "" \
    -file "$CA_CERT_PEM" \
    >/dev/null; then
    echo "Could not export CA cert (alias 'ca') from elastic-stack-ca.p12" >&2
    /usr/share/elasticsearch/jdk/bin/keytool -list -keystore "$CA_P12" -storetype PKCS12 -storepass "" || true
    exit 1
  fi

  echo "Importing CA cert into truststore..."
  /usr/share/elasticsearch/jdk/bin/keytool \
    -importcert \
    -noprompt \
    -alias elastic-stack-ca \
    -file "$CA_CERT_PEM" \
    -keystore "$TRUSTSTORE_P12" \
    -storetype PKCS12 \
    -storepass "$TRUSTSTORE_PASS" \
    >/dev/null

  /usr/share/elasticsearch/jdk/bin/keytool \
    -list \
    -keystore "$TRUSTSTORE_P12" \
    -storetype PKCS12 \
    -storepass "$TRUSTSTORE_PASS" \
    >/dev/null
else
  echo "CA truststore already exists"
fi

if [[ ! -f "$NODE_CERT_P12" ]]; then
  echo "Generating transport cert signed by CA"
  /usr/share/elasticsearch/bin/elasticsearch-certutil cert --silent --ca "$CA_P12" --ca-pass "" --out "$NODE_CERT_P12" --pass ""
else
  echo "Transport cert already exists"
fi

chown -R 1000:0 "$CERTS_DIR"
ls -la "$CERTS_DIR"
