#!/usr/bin/env python3
"""Start frontend, API and worker. PostgreSQL must already be running."""
import os
from pathlib import Path
import signal
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
ENGINE = ROOT / 'engine'
PYTHON = ENGINE / '.venv/bin/python'


def main():
    if not PYTHON.exists():
        sys.exit('Install backend dependencies first: cd engine && uv sync --extra dev')
    if not (ROOT / 'frontend/node_modules').exists():
        sys.exit('Install frontend dependencies first: cd frontend && npm ci')
    subprocess.run([str(ENGINE / '.venv/bin/alembic'), 'upgrade', 'head'], cwd=ENGINE, check=True)
    subprocess.run([str(PYTHON), '-m', 'app.db.seed'], cwd=ENGINE, check=True)
    processes = []
    def stop(*_):
        for process in processes:
            if process.poll() is None:
                os.killpg(process.pid, signal.SIGTERM)
    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    try:
        for args, cwd in [
            ([str(PYTHON), '-m', 'uvicorn', 'app.main:app', '--host', '127.0.0.1', '--port', '8000'], ENGINE),
            ([str(PYTHON), '-m', 'app.jobs.worker'], ENGINE),
            (['npm', 'run', 'dev', '--', '--port', os.environ.get('FRONTEND_PORT', '3001')], ROOT / 'frontend'),
        ]:
            processes.append(subprocess.Popen(args, cwd=cwd, start_new_session=True))
        print('Kiez-py: http://localhost:3001 — Ctrl+C stops API, frontend, and worker.', flush=True)
        while all(p.poll() is None for p in processes):
            time.sleep(.5)
    finally:
        stop()
        for process in processes:
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL)


if __name__ == '__main__':
    main()
