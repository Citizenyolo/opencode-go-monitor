#!/usr/bin/env bash
# Stop OpenCode GO Monitor Dashboard

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PID_FILE="$DIR/monitor.pid"

if [ -f "$PID_FILE" ]; then
  PID=$(cat "$PID_FILE" 2>/dev/null)
  if [ -n "$PID" ] && kill -0 "$PID" 2>/dev/null; then
    CMD=$(ps -p "$PID" -o command= 2>/dev/null || true)
    if [[ "$CMD" == *"server.py"* ]]; then
      kill -15 "$PID" 2>/dev/null || true
      for i in {1..20}; do
        if ! kill -0 "$PID" 2>/dev/null; then break; fi
        sleep 0.1
      done
      if kill -0 "$PID" 2>/dev/null; then
        kill -9 "$PID" 2>/dev/null || true
      fi
      echo "🛑 Stopped monitor server (PID: $PID)"
    else
      echo "⚠️ Process $PID is not server.py. Skipping termination."
    fi
  else
    echo "⚠️ Process $PID was not running."
  fi
  rm -f "$PID_FILE"
else
  # Fallback: check port 7890 if running server.py
  PORT_PID=$(lsof -ti :7890 2>/dev/null | head -n 1)
  if [ -n "$PORT_PID" ]; then
    CMD=$(ps -p "$PORT_PID" -o command= 2>/dev/null || true)
    if [[ "$CMD" == *"server.py"* ]]; then
      kill -15 "$PORT_PID" 2>/dev/null || true
      sleep 0.5
      kill -9 "$PORT_PID" 2>/dev/null || true
      echo "🛑 Stopped monitor server on port 7890 (PID: $PORT_PID)"
    fi
  else
    echo "No running monitor server found on port 7890."
  fi
fi

if launchctl list com.opencode.v6monitor 2>/dev/null | grep -q '"PID"'; then
  echo "ℹ️  Note: com.opencode.v6monitor is loaded in launchd and will restart automatically."
  echo "   To stop it permanently, run: ./remove_autostart.sh"
fi
