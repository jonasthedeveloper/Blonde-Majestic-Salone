#!/bin/bash
# Starts a throw-away server (temp database) and runs the end-to-end API test.
cd "$(dirname "$0")/.."
export DB_PATH=/tmp/bm_test.db PORT=8765 ADMIN_PASSWORD=TestPass123
rm -f /tmp/bm_test.db*
python3 server.py --quiet > /tmp/srv.log 2>&1 &
PID=$!
sleep 1.5
python3 tests/e2e.py http://localhost:8765 owner@salon.local TestPass123
RC=$?
kill $PID 2>/dev/null
exit $RC
