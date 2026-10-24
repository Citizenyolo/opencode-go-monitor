#!/usr/bin/env bash
# Stop OpenCode GO Monitor Dashboard

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PID_FILE="$DIR/monitor.pid"

if [ -f "$PID_FILE" ]; then
  PID=$(cat "$PID_FILE")
  if kill -0 "$PID" 2>/dev/null; then
    kill "$PID"
    echo "🛑 Stopped monitor server (PID: $PID)"
  else
    echo "⚠️ Process $PID was not running."
  fi
  rm -f "$PID_FILE"
else
  # fallback kill by port/name
  pkill -f "opencode_monitor/server.py" && echo "🛑 Stopped monitor server" || echo "No running monitor server found."
fi
