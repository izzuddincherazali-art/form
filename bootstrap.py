"""Create a private team password once, then start the server."""
import os, secrets, runpy
from pathlib import Path
path = Path(os.environ.get('DATABASE_PATH', '/data/sessions.sqlite3')).parent / 'team-password.txt'
if not os.environ.get('APP_PASSWORD'):
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, 'x', opener=lambda p, f: os.open(p, f, 0o600)) as f:
            f.write(secrets.token_urlsafe(24))
    os.environ['APP_PASSWORD'] = path.read_text().strip()
runpy.run_path('server.py', run_name='__main__')
