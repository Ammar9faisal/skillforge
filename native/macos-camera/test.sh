#!/bin/bash
set -euo pipefail
CAPTURE_ROOT="$(cd "$(dirname "$0")" && pwd)"
mkdir -p "$CAPTURE_ROOT/.build/module-cache"
swiftc -parse-as-library -target "$(uname -m)-apple-macos14.0" \
  -module-cache-path "$CAPTURE_ROOT/.build/module-cache" \
  "$CAPTURE_ROOT/FrameForwarder.swift" "$CAPTURE_ROOT/CaptureOptions.swift" "$CAPTURE_ROOT/CaptureOptionsTests.swift" \
  -o "$CAPTURE_ROOT/.build/capture-options-tests"
"$CAPTURE_ROOT/.build/capture-options-tests"
