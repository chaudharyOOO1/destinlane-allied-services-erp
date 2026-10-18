#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

suite="${1:-staff-save}"
case "$suite" in staff-save|travel-expenses|md-accounting) ;; *) echo "Unknown browser suite" >&2; exit 1;; esac

browser="${BROWSER_EXECUTABLE_PATH:-}"
if [ -z "$browser" ]; then
  browser="$(command -v chromium || command -v google-chrome || true)"
fi
if [ -z "$browser" ] || [ ! -x "$browser" ]; then
  echo 'Install Chromium/Chrome or set BROWSER_EXECUTABLE_PATH to its executable.' >&2
  exit 1
fi

test_log="$(mktemp)"
node node_modules/vite/bin/vite.js --host 127.0.0.1 --port 5179 --strictPort >"$test_log" 2>&1 &
server_pid=$!
cleanup() {
  kill "$server_pid" 2>/dev/null || true
  wait "$server_pid" 2>/dev/null || true
  rm -f "$test_log"
}
trap cleanup EXIT
for attempt in {1..40}; do
  if ! kill -0 "$server_pid" 2>/dev/null; then cat "$test_log"; exit 1; fi
  if grep -q "Local:" "$test_log" && curl --silent --fail http://127.0.0.1:5179/ >/dev/null; then break; fi
  sleep 0.25
done
if ! curl --silent --fail http://127.0.0.1:5179/ >/dev/null; then
  cat "$test_log"
  exit 1
fi
BROWSER_EXECUTABLE_PATH="$browser" FRONTEND_TEST_URL=http://127.0.0.1:5179 \
  node --test "tests/${suite}.browser.test.mjs"
