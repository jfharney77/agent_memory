#!/usr/bin/env bash
# Stops whatever start.sh started.
cd "$(dirname "$0")"

for name in backend frontend; do
  pidfile=".run/$name.pid"
  [ -f "$pidfile" ] || continue
  pid=$(cat "$pidfile")
  if kill -0 "$pid" 2>/dev/null; then
    # Negative pid = the whole process group start.sh created with setsid.
    kill -TERM -- "-$pid" 2>/dev/null || kill "$pid" 2>/dev/null || true
    echo "stopped $name ($pid)"
  else
    echo "$name was not running"
  fi
  rm -f "$pidfile"
done
