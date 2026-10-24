#!/usr/bin/env bash
set -e

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PLIST_NAME="com.opencode.v6monitor.plist"
TARGET_DIR="$HOME/Library/LaunchAgents"
TARGET_PLIST="$TARGET_DIR/$PLIST_NAME"
PYTHON_BIN="$(which python3 || echo "/usr/bin/python3")"

echo "⚙️ macOS LaunchAgent autostart beállítása ($DIR)..."

# Ensure ~/Library/LaunchAgents exists
mkdir -p "$TARGET_DIR"

# Stop any running instances first
EXISTING_PID=$(lsof -ti :7890 2>/dev/null || true)
if [ -n "$EXISTING_PID" ]; then
  kill -9 $EXISTING_PID 2>/dev/null || true
  sleep 0.5
fi

# If already loaded in launchctl, unload it first
launchctl unload "$TARGET_PLIST" 2>/dev/null || true

# Generate dynamic plist with absolute paths for the current machine
cat <<EOF > "$TARGET_PLIST"
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.opencode.v6monitor</string>
    <key>ProgramArguments</key>
    <array>
        <string>$PYTHON_BIN</string>
        <string>$DIR/server.py</string>
    </array>
    <key>WorkingDirectory</key>
    <string>$DIR</string>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>StandardOutPath</key>
    <string>$DIR/server.log</string>
    <key>StandardErrorPath</key>
    <string>$DIR/server_err.log</string>
</dict>
</plist>
EOF

# Load into launchctl with auto-start on login
launchctl load -w "$TARGET_PLIST"

echo "=================================================="
echo "🎉 SIKERES BEÁLLÍTÁS — 'Set up and forget forever'!"
echo "=================================================="
echo "✅ A v6 Monitor mostantól a macOS rendszerrel együtt,"
echo "   minden bejelentkezéskor és újraindításkor csendben"
echo "   elindul a háttérben."
echo "✅ Ha bármiért leállna, a macOS azonnal újraindítja."
echo "🌐 Dashboard elérése: http://localhost:7890"
echo "=================================================="
