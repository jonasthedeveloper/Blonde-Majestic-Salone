#!/bin/bash
cd "$(dirname "$0")"
command -v python3 >/dev/null || { echo "Python 3.9+ is required: https://www.python.org/downloads/"; exit 1; }
python3 server.py
