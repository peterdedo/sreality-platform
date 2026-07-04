#!/usr/bin/env bash
curl -s -w "\nHTTP:%{http_code}\n" "http://127.0.0.1:8000/api/listings?page=1&page_size=25&is_active=true" | tail -20
