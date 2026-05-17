#!/usr/bin/env python3
"""Crypto 15-min scanner — called by cron every 90s."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path.home() / '.hermes' / 'scripts'))
from crypto_intel import scan_and_log
result = scan_and_log()
print(f"{result['entries']} entries, {result['markets']} markets")
