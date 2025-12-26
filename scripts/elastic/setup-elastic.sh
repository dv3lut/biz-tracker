#!/usr/bin/env sh
set -eu

if [ -z "${ELASTIC_PASSWORD:-}" ]; then
  echo "ELASTIC_PASSWORD is empty; aborting setup." >&2
  exit 1
fi
if [ -z "${KIBANA_SYSTEM_PASSWORD:-}" ]; then
  echo "KIBANA_SYSTEM_PASSWORD is empty; aborting setup." >&2
  exit 1
fi
if [ -z "${ELASTIC_LOGGER_USERNAME:-}" ] || [ -z "${ELASTIC_LOGGER_PASSWORD:-}" ]; then
  echo "ELASTIC_LOGGER_USERNAME/PASSWORD are empty; aborting setup." >&2
  exit 1
fi
if [ -z "${KIBANA_UI_USERNAME:-}" ] || [ -z "${KIBANA_UI_PASSWORD:-}" ]; then
  echo "KIBANA_UI_USERNAME/PASSWORD are empty; aborting setup." >&2
  exit 1
fi

INDEX_PREFIX="${LOGGING__ELASTICSEARCH__INDEX_PREFIX:-biz-tracker-observability}"
INDEX_PATTERN="${INDEX_PREFIX}-*"

echo "Setting kibana_system password..."
curl -fsS -X POST \
  -u "elastic:${ELASTIC_PASSWORD}" \
  http://biztracker-elasticsearch:9200/_security/user/kibana_system/_password \
  -H 'Content-Type: application/json' \
  -d "{\"password\":\"${KIBANA_SYSTEM_PASSWORD}\"}" \
  >/dev/null

echo "Creating biztracker roles..."
ROLE_WRITER_PAYLOAD=$(printf '{"cluster":[],"indices":[{"names":["%s"],"privileges":["create_index","write","create","index","view_index_metadata"]}]}' "${INDEX_PATTERN}")
ROLE_READER_PAYLOAD=$(printf '{"cluster":[],"indices":[{"names":["%s"],"privileges":["read","view_index_metadata"]}]}' "${INDEX_PATTERN}")

curl -fsS -X PUT \
  -u "elastic:${ELASTIC_PASSWORD}" \
  http://biztracker-elasticsearch:9200/_security/role/biztracker_observability_writer \
  -H 'Content-Type: application/json' \
  -d "${ROLE_WRITER_PAYLOAD}" \
  >/dev/null

curl -fsS -X PUT \
  -u "elastic:${ELASTIC_PASSWORD}" \
  http://biztracker-elasticsearch:9200/_security/role/biztracker_observability_reader \
  -H 'Content-Type: application/json' \
  -d "${ROLE_READER_PAYLOAD}" \
  >/dev/null

echo "Creating backend logger user (${ELASTIC_LOGGER_USERNAME})..."
curl -fsS -X PUT \
  -u "elastic:${ELASTIC_PASSWORD}" \
  "http://biztracker-elasticsearch:9200/_security/user/${ELASTIC_LOGGER_USERNAME}" \
  -H 'Content-Type: application/json' \
  -d "{\"password\":\"${ELASTIC_LOGGER_PASSWORD}\",\"roles\":[\"biztracker_observability_writer\"],\"full_name\":\"BizTracker backend logger\"}" \
  >/dev/null

echo "Creating Kibana UI user (${KIBANA_UI_USERNAME})..."
curl -fsS -X PUT \
  -u "elastic:${ELASTIC_PASSWORD}" \
  "http://biztracker-elasticsearch:9200/_security/user/${KIBANA_UI_USERNAME}" \
  -H 'Content-Type: application/json' \
  -d "{\"password\":\"${KIBANA_UI_PASSWORD}\",\"roles\":[\"kibana_admin\",\"biztracker_observability_reader\"],\"full_name\":\"BizTracker Kibana admin\"}" \
  >/dev/null

echo "Done."
