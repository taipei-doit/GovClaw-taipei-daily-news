#!/bin/bash
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"
STATE_DIR="$DIR/../memory"
mkdir -p "$STATE_DIR"
cat > "$STATE_DIR/heartbeat-state.json" << 'JSON_EOF'
{
  "12pm_fetch_date": "2026-05-25",
  "5pm_pipeline_date": "2026-05-25",
  "lastChecks": {}
}
JSON_EOF
