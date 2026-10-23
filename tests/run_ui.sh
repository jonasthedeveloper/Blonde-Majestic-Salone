#!/bin/bash
cd "$(dirname "$0")/.."
export DB_PATH=/tmp/bm_ui.db PORT=8766 ADMIN_PASSWORD=TestPass123
rm -f /tmp/bm_ui.db*
python3 server.py --quiet > /tmp/srv_ui.log 2>&1 &
PID=$!; sleep 1.5
python3 tests/ui.py http://localhost:8766 owner@salon.local TestPass123; RC=$?
kill $PID 2>/dev/null; tail -n 15 /tmp/srv_ui.log; exit $RC
