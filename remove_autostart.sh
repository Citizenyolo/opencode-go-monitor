#!/usr/bin/env bash
TARGET_PLIST="$HOME/Library/LaunchAgents/com.opencode.v6monitor.plist"

echo "🛑 Autostart eltávolítása..."
launchctl unload "$TARGET_PLIST" 2>/dev/null || true
rm -f "$TARGET_PLIST"
echo "✅ Automatikus indítás sikeresen eltávolítva."
