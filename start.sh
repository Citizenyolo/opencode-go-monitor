#!/usr/bin/env bash
# Start OpenCode GO Monitor Dashboard in background

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PID_FILE="$DIR/monitor.pid"

# 1. Check if already managed and running under macOS launchd
if launchctl list com.opencode.v6monitor 2>/dev/null | grep -q '"PID"'; then
  echo "ℹ️  Monitor is already running via launchd background daemon."
  echo "🌐 Dashboard URL: http://localhost:7890"
  open "http://localhost:7890" 2>/dev/null || true
  exit 0
fi

# 2. Check for existing process on port 7890 and verify identity before killing
EXISTING_PID=$(lsof -ti :7890 2>/dev/null | head -n 1)
if [ -n "$EXISTING_PID" ]; then
  CMD=$(ps -p "$EXISTING_PID" -o command= 2>/dev/null || true)
  if [[ "$CMD" == *"server.py"* ]]; then
    echo "⚠️  Existing monitor process detected (PID: $EXISTING_PID). Terminating gracefully..."
    kill -15 "$EXISTING_PID" 2>/dev/null || true
    for i in {1..30}; do
      if ! kill -0 "$EXISTING_PID" 2>/dev/null; then break; fi
      sleep 0.1
    done
    if kill -0 "$EXISTING_PID" 2>/dev/null; then
      echo "Forcing termination of unresponsive monitor process..."
      kill -9 "$EXISTING_PID" 2>/dev/null || true
    fi
  else
    echo "❌ Error: Port 7890 is in use by another application ($CMD, PID: $EXISTING_PID)."
    echo "Please stop that application or change the monitor PORT before starting."
    exit 1
  fi
fi

if [ -f "$PID_FILE" ]; then
  OLD_PID=$(cat "$PID_FILE" 2>/dev/null)
  if [ -n "$OLD_PID" ] && kill -0 "$OLD_PID" 2>/dev/null; then
    kill -15 "$OLD_PID" 2>/dev/null || true
  fi
  rm -f "$PID_FILE"
fi

echo "🚀 Starting OpenCode GO Fleet Monitor..."
python3 "$DIR/server.py" > "$DIR/server.log" 2>&1 &
PID=$!
echo $PID > "$PID_FILE"

sleep 1
if kill -0 "$PID" 2>/dev/null; then
  echo "✅ Monitor is running natively in background (PID: $PID)"
  echo "🌐 Dashboard URL: http://localhost:7890"
  open "http://localhost:7890" 2>/dev/null || true
else
  echo "❌ Failed to start monitor server. Check logs: $DIR/server.log"
  exit 1
fi
