import os, json, sqlite3, secrets, math
from datetime import datetime
from pathlib import Path
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from http.cookies import SimpleCookie

ROOT = Path(__file__).parent
DB = os.environ.get('DATABASE_PATH', str(ROOT / 'data' / 'sessions.sqlite3'))
TOKEN = os.environ.get('APP_PASSWORD', '')

def connect():
    db = sqlite3.connect(DB)
    db.row_factory = sqlite3.Row
    return db

def initialize():
    Path(DB).parent.mkdir(parents=True, exist_ok=True)
    with connect() as db:
        db.execute('CREATE TABLE IF NOT EXISTS sessions (id INTEGER PRIMARY KEY, host TEXT NOT NULL, start TEXT NOT NULL, end TEXT NOT NULL, gmv_cents INTEGER NOT NULL, views INTEGER NOT NULL, notes TEXT NOT NULL, created TEXT DEFAULT CURRENT_TIMESTAMP)')

def validate(data):
    host = str(data.get('host', '')).strip()
    notes = str(data.get('notes', '')).strip()
    if not host or len(host) > 100 or len(notes) > 1000:
        raise ValueError('Enter a host name (up to 100 characters) and notes under 1,000 characters.')
    start, end = str(data.get('start', '')), str(data.get('end', ''))
    a, b = datetime.fromisoformat(start), datetime.fromisoformat(end)
    if a.tzinfo or b.tzinfo or b <= a:
        raise ValueError('End time must be after start time. Use Malaysia local time.')
    from decimal import Decimal, InvalidOperation
    try:
        money = Decimal(str(data.get('gmv', '')))
        views = Decimal(str(data.get('views', '')))
        if not money.is_finite() or not views.is_finite() or money < 0 or money > 999999999 or views < 0 or views > 2147483647 or views != int(views) or money != money.quantize(Decimal('.01')):
            raise ValueError()
    except (InvalidOperation, ValueError, OverflowError):
        raise ValueError('Enter a valid nonnegative GMV with up to two decimals and a whole-number view count.')
    return host, start, end, int(money * 100), int(views), notes

class Handler(BaseHTTPRequestHandler):
    def reply(self, status, data, kind='application/json'):
        body = json.dumps(data).encode() if kind == 'application/json' else data
        self.send_response(status)
        self.send_header('Content-Type', kind)
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Content-Security-Policy', "default-src 'self'; script-src 'self'; style-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'")
        self.end_headers()
        self.wfile.write(body)

    def authorized(self):
        return not TOKEN or secrets.compare_digest(self.headers.get('Authorization', ''), 'Bearer ' + TOKEN)

    def do_GET(self):
        if self.path == '/api/sessions':
            if not self.authorized():
                return self.reply(401, {'error': 'Enter the team password to access records.'})
            with connect() as db:
                rows = [dict(row) for row in db.execute('SELECT * FROM sessions ORDER BY start DESC, id DESC')]
            return self.reply(200, rows)
        files = {'/': ('index.html', 'text/html; charset=utf-8'), '/app.js': ('app.js', 'text/javascript'), '/style.css': ('style.css', 'text/css')}
        if self.path not in files:
            return self.reply(404, {'error': 'Not found'})
        name, kind = files[self.path]
        self.reply(200, (ROOT / 'public' / name).read_bytes(), kind)

    def do_POST(self):
        if self.path != '/api/sessions':
            return self.reply(404, {'error': 'Not found'})
        if not self.authorized():
            return self.reply(401, {'error': 'Enter the team password to save records.'})
        # Require JSON, so another website cannot submit an ordinary cross-site form.
        if self.headers.get('Content-Type', '').split(';')[0] != 'application/json':
            return self.reply(415, {'error': 'JSON required'})
        try:
            size = int(self.headers.get('Content-Length', '0'))
            if size < 1 or size > 10000:
                raise ValueError('Request size is invalid.')
            data = json.loads(self.rfile.read(size))
            if not isinstance(data, dict):
                raise ValueError('Expected a record object.')
            values = validate(data)
            with connect() as db:
                cursor = db.execute('INSERT INTO sessions (host,start,end,gmv_cents,views,notes) VALUES (?,?,?,?,?,?)', values)
                result = dict(db.execute('SELECT * FROM sessions WHERE id=?', (cursor.lastrowid,)).fetchone())
            return self.reply(201, result)
        except (ValueError, TypeError, KeyError) as error:
            return self.reply(400, {'error': str(error)})

if __name__ == '__main__':
    initialize()
    host = os.environ.get('HOST', '127.0.0.1')
    if host not in ('127.0.0.1', 'localhost') and len(TOKEN) < 12:
        raise SystemExit('Set APP_PASSWORD to at least 12 characters before exposing the server.')
    print('Live Desk running on port ' + os.environ.get('PORT', '8000'), flush=True)
    ThreadingHTTPServer((host, int(os.environ.get('PORT', '8000'))), Handler).serve_forever()
