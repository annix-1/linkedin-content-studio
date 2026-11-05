#!/bin/bash
# Start the Content Studio board automatically when you log in (macOS).
#   bash scripts/install-autostart-mac.sh "/Users/you/ContentStudio"
# Undo:  launchctl bootout gui/$(id -u)/com.contentstudio.board && rm ~/Library/LaunchAgents/com.contentstudio.board.plist
set -euo pipefail
STUDIO="${1:?Pass the Content Studio folder path}"
STUDIO="$(cd "$STUDIO" && pwd)"
case "$STUDIO" in
  "$HOME/Desktop"*|"$HOME/Documents"*|"$HOME/Downloads"*)
    echo "macOS blocks login items from reading Desktop, Documents and Downloads."
    echo "Move the folder first, e.g.: mv \"$STUDIO\" ~/ContentStudio"; exit 1;;
esac
[ -f "$STUDIO/server.py" ] || { echo "No server.py in $STUDIO"; exit 1; }
[ -f "$STUDIO/config.json" ] || { echo "Finish setup first (config.json is missing)."; exit 1; }
PY="$(command -v python3)"
PLIST="$HOME/Library/LaunchAgents/com.contentstudio.board.plist"
mkdir -p "$HOME/Library/LaunchAgents" "$HOME/Library/Logs"
cat > "$PLIST" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>com.contentstudio.board</string>
  <key>ProgramArguments</key><array><string>$PY</string><string>-I</string><string>$STUDIO/server.py</string></array>
  <key>WorkingDirectory</key><string>$STUDIO</string>
  <key>RunAtLoad</key><true/>
  <key>KeepAlive</key><dict><key>SuccessfulExit</key><false/></dict>
  <key>ThrottleInterval</key><integer>30</integer>
  <key>StandardOutPath</key><string>$HOME/Library/Logs/content-studio.log</string>
  <key>StandardErrorPath</key><string>$HOME/Library/Logs/content-studio.log</string>
</dict>
</plist>
EOF
launchctl bootout "gui/$(id -u)/com.contentstudio.board" 2>/dev/null || true
launchctl bootstrap "gui/$(id -u)" "$PLIST"
echo "Content Studio will now start at login. Log: ~/Library/Logs/content-studio.log"
