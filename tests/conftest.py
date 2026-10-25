import functools
import http.server
import os
import socket
import subprocess
import sys
import threading
import time

import httpx
import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url


class QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass


@pytest.fixture(scope="session")
def infrastructure():
    if os.getenv("RUN_INTEGRATION") != "1":
        pytest.skip("RUN_INTEGRATION=1 requiere PostgreSQL y MinIO locales")
    admin_url = make_url(os.environ["DATABASE_URL"])
    test_url = admin_url.set(database="ivostock_test")
    admin_engine = create_engine(admin_url, isolation_level="AUTOCOMMIT")
    with admin_engine.connect() as conn:
        if not conn.scalar(text("SELECT 1 FROM pg_database WHERE datname='ivostock_test'")):
            conn.execute(text("CREATE DATABASE ivostock_test"))
    admin_engine.dispose()
    os.environ["DATABASE_URL"] = test_url.render_as_string(hide_password=False)
    os.environ["S3_BUCKET"] = "snapshots-test"
    os.environ["TASK_LEASE_SECONDS"] = "1"
    subprocess.run([sys.executable, "-m", "alembic", "upgrade", "head"], check=True)
    from ivostock.storage import Snapshots

    Snapshots().initialize()
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    os.environ["SIMULATOR_URL"] = f"http://127.0.0.1:{port}"
    proc = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "ivostock.simulator:app",
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
            "--log-level",
            "error",
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        deadline = time.monotonic() + 20
        while time.monotonic() < deadline:
            try:
                if httpx.get(os.environ["SIMULATOR_URL"] + "/health").status_code == 200:
                    break
            except httpx.HTTPError:
                pass
            time.sleep(0.1)
        else:
            raise RuntimeError("El simulador no inició")
        yield
    finally:
        proc.terminate()
        proc.wait(timeout=10)


@pytest.fixture
def engine(infrastructure):
    from ivostock.db import database, execute

    db = database()
    assert make_url(str(db.url)).database.endswith("_test")
    with db.begin() as conn:
        execute(
            conn,
            "TRUNCATE providers,stores,runs,stock,catalog,links,comparison_events,tasks,attempts,dead_letters,market_calls,worker_heartbeats,sim_stores,sim_items,sim_calls,sim_faults RESTART IDENTITY CASCADE",
        )
    return db


@pytest.fixture
def feed_server(tmp_path):
    handler = functools.partial(QuietHandler, directory=str(tmp_path))
    server = http.server.ThreadingHTTPServer(("0.0.0.0", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    path = tmp_path / "feed.csv"

    def write(stock):
        path.write_text(
            "SKU;stock\n" + "".join(f"{sku};{q}\n" for sku, q in stock.items()), encoding="utf-8"
        )

    stock = {f"A{n:03}": 10 for n in range(50)}
    write(stock)
    yield {
        "url": f"http://127.0.0.1:{server.server_port}/feed.csv",
        "write": write,
        "stock": stock,
        "path": path,
    }
    server.shutdown()
    server.server_close()
    thread.join(timeout=3)
