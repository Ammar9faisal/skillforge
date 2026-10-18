#!/bin/bash
set -euo pipefail
CAPTURE_ROOT="$(cd "$(dirname "$0")" && pwd)"
CAPTURE_BUILD="$CAPTURE_ROOT/.build"
CAPTURE_BIN="$CAPTURE_BUILD/skillforge-capture"
mkdir -p "$CAPTURE_BUILD/module-cache"
if [[ ! -x "$CAPTURE_BIN" || "$CAPTURE_ROOT/SkillForgeCapture.swift" -nt "$CAPTURE_BIN" || "$CAPTURE_ROOT/CaptureOptions.swift" -nt "$CAPTURE_BIN" || "$CAPTURE_ROOT/WindowFrameStream.swift" -nt "$CAPTURE_BIN" || "$CAPTURE_ROOT/FrameForwarder.swift" -nt "$CAPTURE_BIN" ]]; then
  swiftc -parse-as-library -O -target "$(uname -m)-apple-macos14.0" \
    -module-cache-path "$CAPTURE_BUILD/module-cache" \
    -framework AppKit -framework ScreenCaptureKit \
    "$CAPTURE_ROOT/CaptureOptions.swift" "$CAPTURE_ROOT/WindowFrameStream.swift" "$CAPTURE_ROOT/FrameForwarder.swift" "$CAPTURE_ROOT/SkillForgeCapture.swift" -o "$CAPTURE_BIN"
  codesign --force --sign - --identifier local.skillforge.capture "$CAPTURE_BIN"
fi
if [[ "${1:-}" == "build" ]]; then
  echo "Built $CAPTURE_BIN (ad-hoc signed; no developer membership required)."
  exit 0
fi
exec "$CAPTURE_BIN" "$@"
