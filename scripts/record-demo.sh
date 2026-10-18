#!/bin/bash
set -euo pipefail
RECORDER_ROOT="$(cd "$(dirname "$0")" && pwd)"
mkdir -p "$RECORDER_ROOT/.build/module-cache"
RECORDER_BIN="$RECORDER_ROOT/.build/record-demo"
if [[ ! -x "$RECORDER_BIN" || "$RECORDER_ROOT/record-demo.swift" -nt "$RECORDER_BIN" ]]; then
  swiftc -parse-as-library -O -target "$(uname -m)-apple-macos15.0" \
    -module-cache-path "$RECORDER_ROOT/.build/module-cache" \
    -framework AppKit -framework ScreenCaptureKit -framework AVFoundation \
    "$RECORDER_ROOT/record-demo.swift" -o "$RECORDER_BIN"
  codesign --force --sign - --identifier local.skillforge.demo-recorder "$RECORDER_BIN"
fi
exec "$RECORDER_BIN" "$@"
