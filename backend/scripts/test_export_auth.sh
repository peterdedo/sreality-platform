#!/usr/bin/env bash
set -euo pipefail
URL="http://127.0.0.1:8000/api/export/listings?scope=raw&format=json&page=1&page_size=1"
echo -n "dev-local-key: "
curl -s -o /dev/null -w "%{http_code}\n" -H "X-API-Key: dev-local-key" "$URL"
echo -n "wrong-key: "
curl -s -o /dev/null -w "%{http_code}\n" -H "X-API-Key: wrong" "$URL"
