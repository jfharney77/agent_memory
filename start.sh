#!/usr/bin/env bash
# Starts the demo server and the React app together.
#   ./start.sh          then open http://localhost:5180
set -euo pipefail
cd "$(dirname "$0")"

BACKEND_PORT=8077
FRONTEND_PORT=5180

[ -d .venv ] || { echo "No .venv. Run: python3 -m venv .venv && .venv/bin/pip install -r requirements.txt"; exit 1; }
[ -d frontend/node_modules ] || { echo "Installing frontend deps..."; (cd frontend && npm install); }

# This machine runs a lot of dev servers. Refuse to start rather than report
# success while something else answers on our port.
for port in "$BACKEND_PORT" "$FRONTEND_PORT"; do
  if (exec 3<>"/dev/tcp/127.0.0.1/$port") 2>/dev/null; then
    exec 3<&- 2>/dev/null || true
    echo "Port $port is already in use. Run ./stop.sh, or find the process with:"
    echo "  ss -ltnp | grep :$port"
    exit 1
  fi
done

mkdir -p .run

# setsid puts each service in its own process group, so stop.sh can take down
# the whole tree. npm spawns vite spawns node, and killing only the parent
# leaves the dev server holding the port.
setsid .venv/bin/python -m memory_lab.server > .run/backend.log 2>&1 &
echo $! > .run/backend.pid

setsid bash -c 'cd frontend && exec npm run dev' > .run/frontend.log 2>&1 &
echo $! > .run/frontend.pid

for _ in $(seq 20); do
  sleep 0.5
  curl -sf "http://127.0.0.1:$BACKEND_PORT/api/health" > /dev/null && break
done

if ! curl -sf "http://127.0.0.1:$BACKEND_PORT/api/health" > /dev/null; then
  echo "Backend did not come up. See .run/backend.log"
  ./stop.sh > /dev/null 2>&1 || true
  exit 1
fi

echo "backend   http://127.0.0.1:$BACKEND_PORT"
echo "frontend  http://localhost:$FRONTEND_PORT"
echo "logs      .run/backend.log, .run/frontend.log"
echo "stop      ./stop.sh"
