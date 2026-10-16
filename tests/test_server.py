import unittest,tempfile,os,threading,json,urllib.request,urllib.error,http.cookiejar,sqlite3
import server
class PrivateRecordsTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();server.DB=os.path.join(self.tmp.name,'records.sqlite3');server.ADMIN_ALL=True;server.SECURE=False
  server.ATTEMPTS.clear();server.initialize();self.http=server.ThreadingHTTPServer(('127.0.0.1',0),server.Handler);threading.Thread(target=self.http.serve_forever,daemon=True).start();self.base=f'http://127.0.0.1:{self.http.server_port}'
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
 def test_password_change_for_hosts_and_manager(self):
  a,account=self.host('aina');second=self.client();self.call(second,'/api/login',account)
  change=dict(current_password=account['password'],new_password='NewPassword2345',confirm_password='NewPassword2345',user_id=1)
  self.denied(401,self.client(),'/api/change-password',change)
  self.denied(403,a,'/api/change-password',dict(change,current_password='wrong'))
  self.denied(400,a,'/api/change-password',dict(change,confirm_password='different'))
  self.denied(400,a,'/api/change-password',dict(change,new_password='short',confirm_password='short'))
  self.call(a,'/api/change-password',change);self.denied(401,a,'/api/me');self.denied(401,second,'/api/me')
  self.denied(401,self.client(),'/api/login',account)
  self.call(a,'/api/login',dict(username='aina',password=change['new_password']));self.assertEqual(self.call(a,'/api/me')['id'],account['id'])
  from pathlib import Path
  initial=Path(self.tmp.name,'manager-access.txt').read_text().splitlines()[1].split(': ',1)[1]
  change=dict(current_password=initial,new_password='ManagerNew2345',confirm_password='ManagerNew2345')
  self.call(self.admin,'/api/change-password',change);self.denied(401,self.admin,'/api/me');self.call(self.admin,'/api/login',dict(username='manager',password='ManagerNew2345'));self.assertTrue(self.call(self.admin,'/api/me')['is_admin'])
 def test_edit_only_owned_sessions(self):
  a,aa=self.host('aina');b,bb=self.host('budi')
  data=dict(start='2026-10-16T12:00',end='2026-10-16T13:00',gmv='100',views=50,notes='before')
  record=self.call(a,'/api/sessions',data)
  edit=dict(data,id=record['id'],gmv='250.75',notes='after',host='Budi',user_id=bb['id'])
  self.denied(401,self.client(),'/api/edit-session',edit);self.denied(404,b,'/api/edit-session',edit);self.denied(404,self.admin,'/api/edit-session',edit)
  updated=self.call(a,'/api/edit-session',edit);self.assertEqual(updated['gmv_cents'],25075);self.assertEqual(updated['notes'],'after');self.assertEqual(updated['user_id'],aa['id']);self.assertEqual(updated['host'],'Aina')
 def test_email_recovery_verify_reset_and_expiry(self):
  from unittest.mock import patch
  a,account=self.host('aina');sent=[]
  with patch.dict(os.environ,{'SMTP_HOST':'smtp.example.com','SMTP_FROM':'desk@example.com','PUBLIC_URL':'https://live.example.com'}),patch.object(server,'send_link',side_effect=lambda address,token,purpose:sent.append((address,token,purpose))):
   self.denied(403,a,'/api/recovery-email',dict(email='aina@example.com',current_password='wrong'))
   self.call(a,'/api/recovery-email',dict(email='aina@example.com',current_password=account['password']))
   self.assertEqual(self.call(a,'/api/me')['email'],'');token=sent[-1][1]
   self.call(self.client(),'/api/verify-email',dict(token=token));self.denied(400,self.client(),'/api/verify-email',dict(token=token));self.assertEqual(self.call(a,'/api/me')['email'],'aina@example.com')
   public=self.client();known=self.call(public,'/api/forgot-password',dict(email='aina@example.com'));unknown=self.call(public,'/api/forgot-password',dict(email='unknown@example.com'));self.assertEqual(known,unknown)
   token=sent[-1][1]
   with server.connect() as db:self.assertFalse(db.execute('SELECT 1 FROM recovery WHERE token_hash=?',(token,)).fetchone())
   change=dict(token=token,new_password='RecoveredPass234',confirm_password='RecoveredPass234')
   self.denied(400,public,'/api/reset-password',dict(change,confirm_password='wrong'))
   self.call(public,'/api/reset-password',change);self.denied(400,public,'/api/reset-password',change);self.denied(401,a,'/api/me');self.denied(401,public,'/api/login',account)
   self.call(a,'/api/login',dict(username='aina',password='RecoveredPass234'))
   self.call(public,'/api/forgot-password',dict(email='aina@example.com'));token=sent[-1][1]
   with server.connect() as db:db.execute('UPDATE recovery SET expires=0')
   self.denied(400,public,'/api/reset-password',dict(change,token=token))
   # Manager uses the same verified email recovery flow.
   from pathlib import Path
   password=Path(self.tmp.name,'manager-access.txt').read_text().splitlines()[1].split(': ',1)[1]
   self.call(self.admin,'/api/recovery-email',dict(email='manager@example.com',current_password=password));self.call(public,'/api/verify-email',dict(token=sent[-1][1]));self.assertEqual(self.call(self.admin,'/api/me')['email'],'manager@example.com')
 def test_existing_database_migrates(self):
  other=os.path.join(self.tmp.name,'old.sqlite3');old=server.DB
  with sqlite3.connect(other) as db:db.execute('CREATE TABLE sessions(id INTEGER PRIMARY KEY,host TEXT NOT NULL,start TEXT NOT NULL,end TEXT NOT NULL,gmv_cents INTEGER NOT NULL,views INTEGER NOT NULL,notes TEXT NOT NULL,created TEXT DEFAULT CURRENT_TIMESTAMP)')
  server.DB=other
  try:
   server.initialize()
   with server.connect() as db:self.assertIn('user_id',[r['name'] for r in db.execute('PRAGMA table_info(sessions)')])
  finally:server.DB=old
if __name__=='__main__':unittest.main()
