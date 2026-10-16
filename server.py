import os, json, sqlite3, secrets, hashlib, time, re, threading
from datetime import datetime
from pathlib import Path
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from http.cookies import SimpleCookie

ROOT = Path(__file__).parent
DB = os.environ.get('DATABASE_PATH', str(ROOT / 'data' / 'sessions.sqlite3'))
SECURE = os.environ.get('HOST', '127.0.0.1') not in ('127.0.0.1', 'localhost')
ADMIN_ALL = os.environ.get('ADMIN_CAN_VIEW_ALL', 'false').lower() == 'true'
AUTH_LOCK = threading.Lock()
ATTEMPTS = {}

def connect():
    db = sqlite3.connect(DB, timeout=15)
    db.row_factory = sqlite3.Row
    db.execute('PRAGMA foreign_keys=ON')
    return db

def password_hash(password, salt):
    return hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt), n=16384, r=8, p=1).hex()

def generate_password():
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZabcdefghjkmnpqrstuvwxyz23456789"
    return "".join(secrets.choice(alphabet) for _ in range(12))

def add_user(db, username, name, password, admin=0):
    username = str(username).strip().lower()
    name = str(name).strip()
    if not re.fullmatch(r'[a-z0-9][a-z0-9._-]{2,39}', username) or not name or len(name)>100 or len(password)<12:
        raise ValueError('Use a username of 3–40 letters/numbers, a name up to 100 characters and a password of at least 12 characters.')
    salt = secrets.token_hex(16)
    return db.execute('INSERT INTO users(username,name,salt,password_hash,is_admin) VALUES(?,?,?,?,?)', (username,name,salt,password_hash(password,salt),admin)).lastrowid

def initialize():
    Path(DB).parent.mkdir(parents=True, exist_ok=True)
    with connect() as db:
        db.execute('CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY, username TEXT UNIQUE NOT NULL, name TEXT NOT NULL, salt TEXT NOT NULL, password_hash TEXT NOT NULL, is_admin INTEGER NOT NULL DEFAULT 0)')
        db.execute('CREATE TABLE IF NOT EXISTS sessions (id INTEGER PRIMARY KEY, host TEXT NOT NULL, start TEXT NOT NULL, end TEXT NOT NULL, gmv_cents INTEGER NOT NULL, views INTEGER NOT NULL, notes TEXT NOT NULL, created TEXT DEFAULT CURRENT_TIMESTAMP, user_id INTEGER REFERENCES users(id))')
        if 'user_id' not in [r['name'] for r in db.execute('PRAGMA table_info(sessions)')]:
            db.execute('ALTER TABLE sessions ADD COLUMN user_id INTEGER REFERENCES users(id)')
        db.execute('CREATE INDEX IF NOT EXISTS sessions_owner ON sessions(user_id)')
        db.execute('CREATE TABLE IF NOT EXISTS logins(token_hash TEXT PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id), expires INTEGER NOT NULL)')
        if not db.execute('SELECT 1 FROM users WHERE is_admin=1').fetchone():
            password = generate_password()
            username = 'manager'
            access = Path(DB).parent / 'manager-access.txt'
            with open(access, 'w', opener=lambda p,f: os.open(p,f,0o600)) as f:
                f.write('Username: '+username+'\nPassword: '+password+'\n')
            add_user(db,username,'Manager',password,1)

def public_user(user):
    return {k:user[k] for k in ('id','username','name','is_admin')} | {'can_view_all':bool(user['is_admin'] and ADMIN_ALL)}

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
    def reply(self, status, data, kind='application/json', cookie=None):
        body = json.dumps(data).encode() if kind == 'application/json' else data
        self.send_response(status)
        self.send_header('Content-Type', kind)
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Content-Security-Policy', "default-src 'self'; script-src 'self'; style-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'")
        if cookie: self.send_header('Set-Cookie',cookie)
        self.end_headers()
        self.wfile.write(body)

    def auth(self):
        try:
            cookies=SimpleCookie(self.headers.get('Cookie',''))
            token=cookies['live_session'].value
        except (KeyError, ValueError): return None
        hashed=hashlib.sha256(token.encode()).hexdigest()
        with connect() as db:
            return db.execute('SELECT users.* FROM logins JOIN users ON users.id=logins.user_id WHERE token_hash=? AND expires>?',(hashed,int(time.time()))).fetchone()

    def cookie(self, token, clear=False):
        return 'live_session='+token+'; HttpOnly; SameSite=Strict; Path=/; Max-Age='+('0' if clear else '43200')+('; Secure' if SECURE else '')

    def do_GET(self):
        if self.path.startswith('/api/'):
            user=self.auth()
            if not user: return self.reply(401,{'error':'Sign in to access your private records.'})
            if self.path=='/api/me': return self.reply(200,public_user(user))
            if self.path=='/api/sessions':
                with connect() as db:
                    if user['is_admin'] and ADMIN_ALL:
                        rows=db.execute('SELECT * FROM sessions ORDER BY start DESC,id DESC')
                    else:
                        rows=db.execute('SELECT * FROM sessions WHERE user_id=? ORDER BY start DESC,id DESC',(user['id'],))
                    return self.reply(200,[dict(r) for r in rows])
            if self.path=='/api/users' and user['is_admin']:
                with connect() as db:
                    return self.reply(200,[dict(r) for r in db.execute('SELECT id,username,name FROM users WHERE is_admin=0 ORDER BY name')])
            return self.reply(404,{'error':'Not found'})
        files={'/':('index.html','text/html; charset=utf-8'),'/app.js':('app.js','text/javascript'),'/style.css':('style.css','text/css')}
        if self.path not in files: return self.reply(404,{'error':'Not found'})
        name,kind=files[self.path]
        self.reply(200,(ROOT/'public'/name).read_bytes(),kind)

    def do_POST(self):
        if self.headers.get('Content-Type','').split(';')[0]!='application/json':
            return self.reply(415,{'error':'JSON required'})
        # Block cross-site requests even when a browser has an authenticated cookie.
        origin=self.headers.get('Origin')
        if origin and origin.split('://',1)[-1] != self.headers.get('Host'):
            return self.reply(403,{'error':'Cross-site request rejected'})
        try:
            size=int(self.headers.get('Content-Length','0'))
            if not 1<=size<=10000: raise ValueError('Request size is invalid.')
            data=json.loads(self.rfile.read(size))
            if not isinstance(data,dict): raise ValueError('Expected an object.')
            if self.path=='/api/login':
                username=str(data.get('username','')).strip().lower()
                password=str(data.get('password',''))
                if len(username)>100 or len(password)>1000: raise ValueError('Invalid credentials.')
                # Global per-account limit prevents spoofed proxy headers bypassing throttling.
                now=time.time()
                with AUTH_LOCK:
                    times=[t for t in ATTEMPTS.get(username,[]) if now-t<300]
                    if len(times)>=10: return self.reply(429,{'error':'Too many attempts. Try again in five minutes.'})
                    ATTEMPTS[username]=times+[now]
                with connect() as db:
                    user=db.execute('SELECT * FROM users WHERE username=?',(username,)).fetchone()
                    candidate=password_hash(password,user['salt'] if user else '0'*32)
                    if not user or not secrets.compare_digest(candidate,user['password_hash']):
                        return self.reply(401,{'error':'Username or password is incorrect.'})
                    with AUTH_LOCK: ATTEMPTS.pop(username,None)
                    token=secrets.token_urlsafe(32)
                    db.execute('DELETE FROM logins WHERE expires<=?',(int(now),))
                    db.execute('INSERT INTO logins VALUES(?,?,?)',(hashlib.sha256(token.encode()).hexdigest(),user['id'],int(now)+43200))
                return self.reply(200,public_user(user),cookie=self.cookie(token))
            user=self.auth()
            if not user: return self.reply(401,{'error':'Sign in first.'})
            if self.path=='/api/logout':
                cookies=SimpleCookie(self.headers.get('Cookie',''))
                token=cookies['live_session'].value
                with connect() as db: db.execute('DELETE FROM logins WHERE token_hash=?',(hashlib.sha256(token.encode()).hexdigest(),))
                return self.reply(200,{'ok':True},cookie=self.cookie('',True))
            if self.path=='/api/change-password':
                current=str(data.get('current_password',''))
                password=str(data.get('new_password',''))
                if len(current)>1000 or not 12<=len(password)<=128:
                    raise ValueError('Use a new password between 12 and 128 characters.')
                if password!=str(data.get('confirm_password','')):
                    raise ValueError('New passwords do not match.')
                if password==current: raise ValueError('Choose a different new password.')
                now=time.time()
                key='change:'+str(user['id'])
                with AUTH_LOCK:
                    times=[t for t in ATTEMPTS.get(key,[]) if now-t<300]
                    if len(times)>=10: return self.reply(429,{'error':'Too many attempts. Try again in five minutes.'})
                    ATTEMPTS[key]=times+[now]
                with connect() as db:
                    db.execute('BEGIN IMMEDIATE')
                    fresh=db.execute('SELECT * FROM users WHERE id=?',(user['id'],)).fetchone()
                    if not secrets.compare_digest(password_hash(current,fresh['salt']),fresh['password_hash']):
                        return self.reply(403,{'error':'Current password is incorrect.'})
                    salt=secrets.token_hex(16)
                    db.execute('UPDATE users SET salt=?,password_hash=? WHERE id=?',(salt,password_hash(password,salt),user['id']))
                    db.execute('DELETE FROM logins WHERE user_id=?',(user['id'],))
                with AUTH_LOCK: ATTEMPTS.pop(key,None)
                return self.reply(200,{'ok':True},cookie=self.cookie('',True))
            if self.path=='/api/users':
                if not user['is_admin']: return self.reply(403,{'error':'Manager access required.'})
                password=generate_password()
                with connect() as db:
                    uid=add_user(db,data.get('username',''),data.get('name',''),password)
                return self.reply(201,{'id':uid,'username':str(data['username']).strip().lower(),'password':password})
            if self.path=='/api/assign':
                if not user['is_admin'] or not ADMIN_ALL: return self.reply(403,{'error':'Manager access required.'})
                with connect() as db:
                    target=db.execute('SELECT * FROM users WHERE id=? AND is_admin=0',(data.get('user_id'),)).fetchone()
                    if not target: raise ValueError('Choose a valid host account.')
                    cursor=db.execute('UPDATE sessions SET user_id=?,host=? WHERE id=? AND user_id IS NULL',(target['id'],target['name'],data.get('id')))
                    if not cursor.rowcount: raise ValueError('Only unassigned legacy records can be assigned.')
                return self.reply(200,{'ok':True})
            if self.path!='/api/sessions': return self.reply(404,{'error':'Not found'})
            # Identity is always derived from the login, never a submitted host/user_id.
            data['host']=user['name']
            values=validate(data)
            with connect() as db:
                cursor=db.execute('INSERT INTO sessions(host,start,end,gmv_cents,views,notes,user_id) VALUES(?,?,?,?,?,?,?)',(*values,user['id']))
                result=dict(db.execute('SELECT * FROM sessions WHERE id=?',(cursor.lastrowid,)).fetchone())
            return self.reply(201,result)
        except sqlite3.IntegrityError:
            return self.reply(409,{'error':'That username is already taken.'})
        except (ValueError,TypeError,KeyError,OverflowError) as error:
            return self.reply(400,{'error':str(error)})

if __name__=='__main__':
    initialize()
    print('Live Desk private accounts running on port '+os.environ.get('PORT','8000'),flush=True)
    ThreadingHTTPServer((os.environ.get('HOST','127.0.0.1'),int(os.environ.get('PORT','8000'))),Handler).serve_forever()
