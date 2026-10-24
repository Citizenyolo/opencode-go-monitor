#!/usr/bin/env bash
# Start OpenCode GO Monitor Dashboard in background

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PID_FILE="$DIR/monitor.pid"

# Kill any existing process on port 7890
EXISTING_PID=$(lsof -ti :7890 2>/dev/null)
if [ -n "$EXISTING_PID" ]; then
  kill -9 $EXISTING_PID 2>/dev/null || true
  sleep 0.5
fi

if [ -f "$PID_FILE" ]; then
  OLD_PID=$(cat "$PID_FILE" 2>/dev/null)
  if [ -n "$OLD_PID" ]; then
    kill -9 $OLD_PID 2>/dev/null || true
  fi
  rm -f "$PID_FILE"
fi

echo "🚀 Starting OpenCode GO & OpenAI v6 Monitor..."
python3 "$DIR/server.py" > "$DIR/server.log" 2>&1 &
PID=$!
echo $PID > "$PID_FILE"

sleep 1
echo "✅ Monitor is running natively in background (PID: $PID)"
echo "🌐 Dashboard URL: http://localhost:7890"
open "http://localhost:7890" 2>/dev/null || true
