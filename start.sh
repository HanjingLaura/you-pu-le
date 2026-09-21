#!/usr/bin/env bash
set -euo pipefail
root="$(cd "$(dirname "$0")" && pwd)"
unset HTTP_PROXY HTTPS_PROXY http_proxy https_proxy ALL_PROXY all_proxy || true

backend_py="$root/backend/.venv/bin/python"
if [[ ! -x "$backend_py" ]]; then
  backend_py="${PYTHON:-python3}"
fi

(cd "$root/backend" && exec "$backend_py" -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload) &
(cd "$root/frontend" && exec npm run dev -- --hostname 0.0.0.0 --port 3000) &

echo "Backend: http://127.0.0.1:8000  (also proxied through the frontend)"
echo "Frontend: http://localhost:3000"
wait
