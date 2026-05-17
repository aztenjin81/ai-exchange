"""
Hermes PostgreSQL helper — reusable connection for agent scripts.
Import and call get_conn() to get a psycopg2 connection to the hermes DB.

Usage:
    from hermes_db import get_conn, query, query_one

    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT count(*) FROM vm_metrics")
    print(cur.fetchone())

    # Convenience:
    rows = query("SELECT * FROM vm_metrics LIMIT 5")
    row  = query_one("SELECT max(checked_at) FROM vm_metrics")
"""

import os
import psycopg2

_URI = None


def _load_uri():
    """Load the PG URI from environment, trying ~/.hermes/env first."""
    global _URI
    if _URI:
        return _URI

    # Try to source the env file if HERMES_PG_URI isn't set
    if not os.environ.get("HERMES_PG_URI"):
        env_file = os.path.expanduser("~/.hermes/env")
        if os.path.exists(env_file):
            with open(env_file) as f:
                for line in f:
                    line = line.strip()
                    if line.startswith("export HERMES_PG_URI="):
                        val = line.split("=", 1)[1].strip().strip("'\"")
                        os.environ["HERMES_PG_URI"] = val
                        break

    _URI = os.environ.get("HERMES_PG_URI")
    return _URI


def get_conn():
    """Return a psycopg2 connection to the hermes database."""
    uri = _load_uri()
    if not uri:
        raise RuntimeError("HERMES_PG_URI not set — check ~/.hermes/env")
    return psycopg2.connect(uri)


def query(sql, params=None):
    """Execute SELECT and return all rows as a list."""
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute(sql, params)
        rows = cur.fetchall()
        cur.close()
        return rows
    finally:
        conn.close()


def query_one(sql, params=None):
    """Execute SELECT and return one row or None."""
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute(sql, params)
        row = cur.fetchone()
        cur.close()
        return row
    finally:
        conn.close()


def execute(sql, params=None):
    """Execute INSERT/UPDATE/DELETE and commit. Returns rowcount."""
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute(sql, params)
        conn.commit()
        count = cur.rowcount
        cur.close()
        return count
    finally:
        conn.close()
