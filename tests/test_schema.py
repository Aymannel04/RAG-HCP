import sqlite3
from pathlib import Path


def test_schema_sql_est_valide_et_cree_les_trois_tables():
    schema_path = Path(__file__).resolve().parent.parent / "db" / "schema.sql"
    conn = sqlite3.connect(":memory:")
    conn.executescript(schema_path.read_text(encoding="utf-8"))

    tables = {
        row[0]
        for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
    }
    assert {"document", "chunk", "indicateur"} <= tables
    conn.close()
