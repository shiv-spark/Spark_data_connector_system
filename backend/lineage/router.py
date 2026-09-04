"""
Data Lineage Router
────────────────────
Tracks Source → Pipeline → Target table (and column-level) relationships
across every ingest, regardless of connector type. Follows the same shape
as quality/router.py:

  - owns its own tables (lineage_nodes / lineage_edges / lineage_run_events),
    created idempotently via _ensure_tables(), same pattern as
    quality_runs/quality_results in quality/router.py
  - record_lineage() is called from loaders/db_loader.py right after a
    load_to_db() attempt (success or failure) — NOT from each individual
    connector, so every connector (csv, salesforce, hubspot, zoho, ...) is
    covered by one hook point with no per-connector wiring needed
  - column lineage is same-name propagation: since every load is a full-row
    copy of the source's columns into the target table, a column reaching
    the target table came from the identically-named source column. No SQL/
    SOQL parsing needed.

Endpoints
---------
GET  /lineage/graph                    full graph, or an N-hop neighbourhood around ?focus=<node name>
GET  /lineage/table/{table_name}       upstream sources + recent run events for one target table
POST /lineage/backfill                 one-time seed from existing pipeline_metrics history (safe to re-run)
"""

import os
from typing import List, Optional

import psycopg2
import psycopg2.extras
from fastapi import APIRouter, HTTPException

router = APIRouter(prefix="/lineage", tags=["Data Lineage"])

# ── Postgres connection for the lineage module's OWN tables ───────────────
# Same DB as pipeline_runs / pipeline_metrics / quality_runs elsewhere in
# this project — lineage just gets its own tables in it, not a new database.
DB_CONFIG = {
    "host":     os.getenv("DB_HOST", "postgres"),
    "database": os.getenv("DB_NAME", "airflow"),
    "user":     os.getenv("DB_USER", "airflow"),
    "password": os.getenv("DB_PASSWORD", "airflow"),
    "port":     os.getenv("DB_PORT", "5432"),
}


def _get_conn():
    return psycopg2.connect(**DB_CONFIG)


# Sentinel used for `system` on the warehouse (target) side of every edge —
# i.e. table nodes and their column nodes. Postgres 13 (what this project
# runs) treats NULL as distinct-from-itself in UNIQUE constraints, so if
# `system` were left NULL here, ON CONFLICT (node_type, system, name) would
# never actually match on a repeat run: every scheduled pipeline run would
# silently INSERT a brand-new "table" node instead of upserting the
# existing one, fragmenting the graph one run at a time. Using a real,
# non-NULL value sidesteps that (Postgres 15+'s UNIQUE NULLS NOT DISTINCT
# would be the other fix, but isn't available on 13).
WAREHOUSE_SYSTEM = "warehouse"


def _ensure_tables():
    """Idempotent — matches the CREATE TABLE IF NOT EXISTS pattern used
    everywhere else in this project (see quality/router.py _ensure_tables,
    main.py ensure_connections_table)."""
    conn = _get_conn()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS lineage_nodes (
            node_id   SERIAL PRIMARY KEY,
            node_type VARCHAR(20) NOT NULL,   -- 'source' | 'table' | 'column'
            system    VARCHAR(50),            -- connector_type: csv/salesforce/postgres/... ; NULL for table/column nodes on the warehouse side
            name      TEXT NOT NULL,          -- file path/URL/object name, "table_name", or "table_name.column"
            parent_id INTEGER REFERENCES lineage_nodes(node_id) ON DELETE CASCADE,  -- column node -> its table/source node
            UNIQUE(node_type, system, name)
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS lineage_edges (
            edge_id     SERIAL PRIMARY KEY,
            src_node_id INTEGER NOT NULL REFERENCES lineage_nodes(node_id) ON DELETE CASCADE,
            tgt_node_id INTEGER NOT NULL REFERENCES lineage_nodes(node_id) ON DELETE CASCADE,
            pipeline_id VARCHAR(200),          -- nullable: direct (non-scheduled) ingests have none
            first_seen  TIMESTAMPTZ NOT NULL DEFAULT now(),
            last_seen   TIMESTAMPTZ NOT NULL DEFAULT now(),
            UNIQUE(src_node_id, tgt_node_id, pipeline_id)
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS lineage_run_events (
            id          SERIAL PRIMARY KEY,
            edge_id     INTEGER NOT NULL REFERENCES lineage_edges(edge_id) ON DELETE CASCADE,
            pipeline_id VARCHAR(200),
            rows_loaded INTEGER,
            status      VARCHAR(20),
            ran_at      TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)
    conn.commit()
    cur.close()
    conn.close()


def _upsert_node(cur, node_type: str, system: Optional[str], name: str, parent_id: Optional[int] = None) -> int:
    cur.execute(
        """
        INSERT INTO lineage_nodes (node_type, system, name, parent_id)
        VALUES (%s, %s, %s, %s)
        ON CONFLICT (node_type, system, name)
        DO UPDATE SET parent_id = COALESCE(lineage_nodes.parent_id, EXCLUDED.parent_id)
        RETURNING node_id
        """,
        (node_type, system, name, parent_id),
    )
    row = cur.fetchone()
    # Works whether `cur` is a plain tuple cursor or a RealDictCursor —
    # record_lineage() uses the former, the read endpoints use the latter.
    return row["node_id"] if isinstance(row, dict) else row[0]


def _upsert_edge(cur, src_node_id: int, tgt_node_id: int, pipeline_id: Optional[str]) -> int:
    cur.execute(
        """
        INSERT INTO lineage_edges (src_node_id, tgt_node_id, pipeline_id)
        VALUES (%s, %s, %s)
        ON CONFLICT (src_node_id, tgt_node_id, pipeline_id)
        DO UPDATE SET last_seen = now()
        RETURNING edge_id
        """,
        (src_node_id, tgt_node_id, pipeline_id),
    )
    row = cur.fetchone()
    return row["edge_id"] if isinstance(row, dict) else row[0]


# ── Write path — called from loaders/db_loader.py ─────────────────────────
def record_lineage(
    connector_type: Optional[str],
    source_name: Optional[str],
    table_name: Optional[str],
    pipeline_id: Optional[str],
    columns: Optional[List[str]] = None,
    rows_loaded: int = 0,
    status: str = "SUCCESS",
):
    """Upserts the source node, target-table node, the edge between them,
    a run event, and (for a successful load) same-name column edges.

    Deliberately never raises — a bug in lineage capture should never take
    down an ingest run. Any failure here is logged and swallowed, same as
    the quality gates in utils/ingest_runner.py do for their own errors.
    """
    if not table_name:
        return
    try:
        _ensure_tables()
        conn = _get_conn()
        cur = conn.cursor()
        raw_source = (source_name or "").strip()
        if not raw_source or raw_source.endswith("/None"):
            raw_source = f"unknown:{connector_type or 'source'}"
        source_display = raw_source
        src_id = _upsert_node(cur, "source", connector_type or "unknown", source_display)
        tgt_id = _upsert_node(cur, "table", WAREHOUSE_SYSTEM, table_name)
        edge_id = _upsert_edge(cur, src_id, tgt_id, pipeline_id)

        cur.execute(
            """
            INSERT INTO lineage_run_events (edge_id, pipeline_id, rows_loaded, status)
            VALUES (%s, %s, %s, %s)
            """,
            (edge_id, pipeline_id, rows_loaded, status),
        )

        # ── Column-level lineage: same-name propagation ──────────────────
        # Only recorded for loads that actually reached the table — a
        # FAILED run before any columns were written has nothing to map.
        if status == "SUCCESS":
            for col in (columns or []):
                src_col_id = _upsert_node(cur, "column", connector_type or "unknown", f"{source_display}.{col}", parent_id=src_id)
                tgt_col_id = _upsert_node(cur, "column", WAREHOUSE_SYSTEM, f"{table_name}.{col}", parent_id=tgt_id)
                _upsert_edge(cur, src_col_id, tgt_col_id, pipeline_id)

        conn.commit()
        cur.close()
        conn.close()
    except Exception as e:
        # Lineage is observability, not a load-path dependency.
        print(f"[lineage] record_lineage failed (non-fatal): {e}")


# ── Read API ────────────────────────────────────────────────────────────

@router.get("/graph")
def get_lineage_graph(focus: Optional[str] = None):
    """Full graph (source/table nodes only — columns omitted for readability),
    or the connected neighbourhood around a single node when `focus` (a node
    name, e.g. a table name or a source's display name) is given."""
    _ensure_tables()
    conn = _get_conn()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    if focus:
        cur.execute(
            """
            WITH RECURSIVE neighborhood(node_id) AS (
                SELECT node_id FROM lineage_nodes WHERE name = %s
                UNION
                SELECT CASE WHEN e.src_node_id = n.node_id THEN e.tgt_node_id ELSE e.src_node_id END
                FROM lineage_edges e
                JOIN neighborhood n ON n.node_id IN (e.src_node_id, e.tgt_node_id)
            )
            SELECT DISTINCT node_id FROM neighborhood
            """,
            (focus,),
        )
        node_ids = [r["node_id"] for r in cur.fetchall()]
        if not node_ids:
            cur.close()
            conn.close()
            raise HTTPException(status_code=404, detail=f"No lineage node named '{focus}'")
        cur.execute(
            "SELECT * FROM lineage_nodes WHERE node_id = ANY(%s) AND node_type != 'column'",
            (node_ids,),
        )
        nodes = cur.fetchall()
        cur.execute(
            "SELECT * FROM lineage_edges WHERE src_node_id = ANY(%s) AND tgt_node_id = ANY(%s)",
            (node_ids, node_ids),
        )
        edges = cur.fetchall()
    else:
        cur.execute("SELECT * FROM lineage_nodes WHERE node_type != 'column'")
        nodes = cur.fetchall()
        cur.execute("""
            SELECT e.* FROM lineage_edges e
            JOIN lineage_nodes s ON s.node_id = e.src_node_id
            JOIN lineage_nodes t ON t.node_id = e.tgt_node_id
            WHERE s.node_type != 'column' AND t.node_type != 'column'
        """)
        edges = cur.fetchall()

    cur.close()
    conn.close()
    return {"nodes": nodes, "edges": edges}


@router.get("/table/{table_name}")
def get_table_lineage(table_name: str):
    """Upstream sources + recent run events for one target table — what the
    Pipelines page's 'N sources → this table' badge / drill-in panel calls."""
    _ensure_tables()
    conn = _get_conn()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    cur.execute("SELECT node_id FROM lineage_nodes WHERE node_type = 'table' AND name = %s", (table_name,))
    row = cur.fetchone()
    if not row:
        cur.close()
        conn.close()
        raise HTTPException(status_code=404, detail=f"No lineage recorded for table '{table_name}'")
    tgt_id = row["node_id"]

    cur.execute(
        """
        SELECT e.edge_id, e.pipeline_id, e.first_seen, e.last_seen,
               s.system AS source_system, s.name AS source_name
        FROM lineage_edges e
        JOIN lineage_nodes s ON s.node_id = e.src_node_id
        WHERE e.tgt_node_id = %s
        ORDER BY e.last_seen DESC
        """,
        (tgt_id,),
    )
    sources = cur.fetchall()

    for src in sources:
        cur.execute(
            """
            SELECT rows_loaded, status, ran_at FROM lineage_run_events
            WHERE edge_id = %s ORDER BY ran_at DESC LIMIT 10
            """,
            (src["edge_id"],),
        )
        src["recent_runs"] = cur.fetchall()

    cur.close()
    conn.close()
    return {"table": table_name, "sources": sources}


@router.post("/backfill")
def backfill_from_pipeline_metrics():
    """One-time seed: build lineage edges from existing pipeline_metrics
    history so the graph isn't empty on day 1. Safe to re-run — every write
    goes through the same upsert helpers record_lineage() uses."""
    _ensure_tables()
    conn = _get_conn()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    cur.execute("""
        SELECT DISTINCT ON (pipeline_id, table_name, connector_type, file_name)
               pipeline_id, table_name, connector_type, file_name, status,
               rows_inserted, logged_at
        FROM pipeline_metrics
        WHERE table_name IS NOT NULL
        ORDER BY pipeline_id, table_name, connector_type, file_name, logged_at DESC
    """)
    rows = cur.fetchall()

    seeded = 0
    for row in rows:
        source_display = row["file_name"] or f"unknown:{row['connector_type'] or 'source'}"
        src_id = _upsert_node(cur, "source", row["connector_type"] or "unknown", source_display)
        tgt_id = _upsert_node(cur, "table", WAREHOUSE_SYSTEM, row["table_name"])
        edge_id = _upsert_edge(cur, src_id, tgt_id, row["pipeline_id"])
        cur.execute(
            """
            INSERT INTO lineage_run_events (edge_id, pipeline_id, rows_loaded, status, ran_at)
            VALUES (%s, %s, %s, %s, %s)
            """,
            (edge_id, row["pipeline_id"], row["rows_inserted"], row["status"], row["logged_at"]),
        )
        seeded += 1

    conn.commit()
    cur.close()
    conn.close()
    return {"status": "SUCCESS", "edges_seeded": seeded}