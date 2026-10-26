"""Run DOM/API integration tests on disposable data in the same process network.

Not a browser screenshot test and never touches real learner accounts.
First: npm --prefix tests/graphics-ui ci
"""
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import threading
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main():
    import uvicorn
    from backend.graphics_server import create_app
    with tempfile.TemporaryDirectory() as tmp:
        app = create_app(Path(tmp) / 'graphics.sqlite3', bootstrap=False)
        store = app.state.store
        for name, role in [('ui-student', 'student'), ('ui-peer', 'student'), ('ui-teacher', 'teacher'), ('ui-admin', 'admin')]:
            store.create_user(name, 'Unit-test-graphics-1234', role, name)
        with store.tx() as c:
            c.execute('INSERT INTO graphics_teams(name,created_by) VALUES (?,?)', ('UI test team', 3))
            c.executemany('INSERT INTO graphics_members VALUES (?,?,?)', [(1, 1, 0), (1, 2, 1)])
        sock = socket.socket()
        sock.bind(('127.0.0.1', 0))
        port = sock.getsockname()[1]
        server = uvicorn.Server(uvicorn.Config(app, log_level='error'))
        thread = threading.Thread(target=server.run, kwargs={'sockets': [sock]}, daemon=True)
        thread.start()
        try:
            for _ in range(100):
                if server.started:
                    break
                time.sleep(.02)
            if not server.started:
                raise RuntimeError('Test server failed to start')
            result = subprocess.run(['node', '--test', 'tests/graphics-ui/graphics.test.mjs'], cwd=ROOT,
                                    env={**os.environ, 'GRAPHICS_TEST_URL': f'http://127.0.0.1:{port}'})
            return result.returncode
        finally:
            server.should_exit = True
            thread.join(5)
            sock.close()
            store.conn.close()


if __name__ == '__main__':
    raise SystemExit(main())
