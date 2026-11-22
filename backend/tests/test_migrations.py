import os
import sqlite3
import subprocess
import sys
from pathlib import Path


def test_existing_development_database_upgrades_without_recreating_tables(tmp_path: Path):
    backend = Path(__file__).resolve().parents[1]
    database = tmp_path / "legacy.db"
    env = {**os.environ, "DATABASE_URL": f"sqlite:///{database.as_posix()}"}
    subprocess.run([sys.executable, "-m", "alembic", "upgrade", "0001_initial"],
                   cwd=backend, env=env, check=True, capture_output=True)
    with sqlite3.connect(database) as connection:
        connection.execute("INSERT INTO products (id, tenant_id, sku, name, category, description, status, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                           ("legacy-product", "demo", "LEGACY-1", "历史产品", "配件", "", "draft", "2026-01-01"))
        connection.execute("DROP TABLE alembic_version")
    subprocess.run([sys.executable, "-m", "app.cli", "migrate"],
                   cwd=backend, env=env, check=True, capture_output=True)
    with sqlite3.connect(database) as connection:
        assert connection.execute("SELECT COUNT(*) FROM products WHERE id='legacy-product'").fetchone()[0] == 1
        assert connection.execute("SELECT version_num FROM alembic_version").fetchone()[0] == "0017_repair_entry_hash"
        assert "group_id" in {row[1] for row in connection.execute("PRAGMA table_info(products)")}
        assert "users" in {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}


def test_repairs_database_with_missing_workflow_entry_hash(tmp_path: Path):
    backend = Path(__file__).resolve().parents[1]
    database = tmp_path / 'missing-entry-hash.db'
    env = {**os.environ, 'DATABASE_URL': f'sqlite:///{database.as_posix()}'}
    subprocess.run([sys.executable, '-m', 'alembic', 'upgrade', '0016_collection_v1'],
                   cwd=backend, env=env, check=True, capture_output=True)
    with sqlite3.connect(database) as connection:
        connection.execute('ALTER TABLE workflows DROP COLUMN entry_hash')
        connection.execute("INSERT INTO hotspots (id, tenant_id, title, summary, content_type, source_kind, industry, created_at) VALUES ('kept', 'demo', '保留热点', '', 'text', 'manual', '通用', '2026-01-01')")
    subprocess.run([sys.executable, '-m', 'app.cli', 'migrate'],
                   cwd=backend, env=env, check=True, capture_output=True)
    with sqlite3.connect(database) as connection:
        assert 'entry_hash' in {row[1] for row in connection.execute('PRAGMA table_info(workflows)')}
        assert connection.execute("SELECT COUNT(*) FROM hotspots WHERE id='kept'").fetchone()[0] == 1
