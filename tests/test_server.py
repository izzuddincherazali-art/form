import unittest,tempfile,os,threading,json,urllib.request,urllib.error,http.cookiejar,sqlite3
import server
class PrivateRecordsTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();server.DB=os.path.join(self.tmp.name,'records.sqlite3');server.ADMIN_ALL=True;server.SECURE=False
  server.initialize();self.http=server.ThreadingHTTPServer(('127.0.0.1',0),server.Handler);threading.Thread(target=self.http.serve_forever,daemon=True).start();self.base=f'http://127.0.0.1:{self.http.server_port}'
  self.admin=self.client();access=open(os.path.join(self.tmp.name,'manager-access.txt')).read().splitlines();self.call(self.admin,'/api/login',{'username':'manager','password':access[1].split(': ',1)[1]})
 def tearDown(self):self.http.shutdown();self.http.server_close();self.tmp.cleanup()
 def client(self):return urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
 def call(self,client,path,data=None,headers=None):
  h={'Content-Type':'application/json'};h.update(headers or {});req=urllib.request.Request(self.base+path,data=json.dumps(data).encode() if data is not None else None,headers=h)
  with client.open(req) as response:return json.load(response)
 def denied(self,status,client,path,data=None,headers=None):
  with self.assertRaises(urllib.error.HTTPError) as err:self.call(client,path,data,headers)
  self.assertEqual(err.exception.code,status)
 def host(self,username):
  account=self.call(self.admin,'/api/users',{'username':username,'name':username.title()});client=self.client();self.call(client,'/api/login',account);return client,account
 def test_host_isolation_admin_and_forgery(self):
  a,aa=self.host('aina');b,bb=self.host('budi');anonymous=self.client();data=dict(start='2026-10-16T22:00',end='2026-10-17T01:00',gmv='123.45',views='1200',notes='Private A',host='Budi',user_id=bb['id'])
  record=self.call(a,'/api/sessions',data);self.assertEqual(record['host'],'Aina');self.assertEqual(record['user_id'],aa['id']);self.assertEqual(self.call(b,'/api/sessions'),[]);self.assertEqual(len(self.call(a,'/api/sessions')),1);self.assertEqual(len(self.call(self.admin,'/api/sessions')),1)
  self.denied(401,anonymous,'/api/sessions');self.denied(401,anonymous,'/api/sessions',headers={'Authorization':'Bearer old-team-password'});self.denied(403,a,'/api/users',{'username':'hacker','name':'Hacker'});self.denied(404,a,'/api/users');self.denied(403,a,'/api/sessions',data,{'Origin':'https://evil.example'})
  self.call(a,'/api/logout',{});self.denied(401,a,'/api/sessions')
  for field,value in [('gmv','NaN'),('views','1.5'),('end',data['start'])]:self.denied(400,b,'/api/sessions',dict(data,**{field:value}))
  server.initialize();self.assertEqual(len(self.call(self.admin,'/api/sessions')),1)
 def test_legacy_records_not_claimed_by_name(self):
  with server.connect() as db:db.execute("INSERT INTO sessions(host,start,end,gmv_cents,views,notes) VALUES('Aina','2026-10-16T12:00','2026-10-16T13:00',500,10,'legacy')")
  a,account=self.host('aina');self.assertEqual(self.call(a,'/api/sessions'),[]);record=self.call(self.admin,'/api/sessions')[0];self.call(self.admin,'/api/assign',{'id':record['id'],'user_id':account['id']});self.assertEqual(len(self.call(a,'/api/sessions')),1);self.denied(400,self.admin,'/api/assign',{'id':record['id'],'user_id':account['id']})
 def test_passwords_hashed_and_sessions_expire(self):
  a,account=self.host('aina')
  with server.connect() as db:
   row=db.execute('SELECT * FROM users WHERE username=?',('aina',)).fetchone();self.assertNotEqual(row['password_hash'],account['password']);db.execute('UPDATE logins SET expires=0 WHERE user_id=?',(account['id'],))
  self.denied(401,a,'/api/me')
 def test_existing_database_migrates(self):
  other=os.path.join(self.tmp.name,'old.sqlite3');old=server.DB
  with sqlite3.connect(other) as db:db.execute('CREATE TABLE sessions(id INTEGER PRIMARY KEY,host TEXT NOT NULL,start TEXT NOT NULL,end TEXT NOT NULL,gmv_cents INTEGER NOT NULL,views INTEGER NOT NULL,notes TEXT NOT NULL,created TEXT DEFAULT CURRENT_TIMESTAMP)')
  server.DB=other
  try:
   server.initialize()
   with server.connect() as db:self.assertIn('user_id',[r['name'] for r in db.execute('PRAGMA table_info(sessions)')])
  finally:server.DB=old
if __name__=='__main__':unittest.main()
