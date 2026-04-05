"""Initialize the Soma database schema on a remote TimescaleDB instance."""

import psycopg2
import os
from pathlib import Path

DATABASE_URL = os.environ.get(
    "SOMA_DATABASE_URL",
    "postgres://tsdbadmin:kzw7n8a63xeml4d3@h80k79ebls.pb6qgbg1iv.tsdb.cloud.timescale.com:36982/tsdb?sslmode=require"
)

def main():
    # Read the init.sql file
    init_sql_path = Path(__file__).parent.parent / "core" / "sql" / "init.sql"

    with open(init_sql_path, "r") as f:
        init_sql = f.read()

    print(f"Connecting to database...")
    conn = psycopg2.connect(DATABASE_URL)
    conn.autocommit = True
    cur = conn.cursor()

    # TimescaleDB extension should already be enabled on Timescale Cloud
    # But the CREATE EXTENSION will just skip if it exists

    print("Running schema initialization...")

    # Split by semicolons and run each statement
    # (needed because psycopg2 doesn't handle multi-statement well)
    statements = init_sql.split(';')

    for i, stmt in enumerate(statements):
        stmt = stmt.strip()
        if not stmt:
            continue
        try:
            cur.execute(stmt)
            print(f"  [{i+1}/{len(statements)}] OK")
        except psycopg2.errors.DuplicateTable:
            print(f"  [{i+1}/{len(statements)}] Table already exists, skipping")
        except psycopg2.errors.DuplicateObject:
            print(f"  [{i+1}/{len(statements)}] Object already exists, skipping")
        except psycopg2.errors.UniqueViolation:
            print(f"  [{i+1}/{len(statements)}] Data already exists, skipping")
        except Exception as e:
            print(f"  [{i+1}/{len(statements)}] Warning: {e}")

    # Verify tables exist
    cur.execute("""
        SELECT table_name FROM information_schema.tables
        WHERE table_schema = 'public'
        ORDER BY table_name
    """)
    tables = [row[0] for row in cur.fetchall()]

    print(f"\nTables created: {', '.join(tables)}")

    # Check biomarker count
    cur.execute("SELECT COUNT(*) FROM biomarker_types")
    biomarker_count = cur.fetchone()[0]
    print(f"Biomarker types seeded: {biomarker_count}")

    cur.close()
    conn.close()
    print("\nDatabase initialized successfully!")

if __name__ == "__main__":
    main()
