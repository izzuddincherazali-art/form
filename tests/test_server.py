import unittest, tempfile, os, threading, json, urllib.request, urllib.error
import server

class SessionTests(unittest.TestCase):
    def test_roundtrip_and_validation(self):
        with tempfile.TemporaryDirectory() as folder:
            server.DB = os.path.join(folder, 'records.sqlite3')
            server.TOKEN = 'test-password-long'
            server.initialize()
            http = server.ThreadingHTTPServer(('127.0.0.1',0),server.Handler)
            thread = threading.Thread(target=http.serve_forever,daemon=True); thread.start()
            url = f'http://127.0.0.1:{http.server_port}/api/sessions'
            def request(data=None, token=server.TOKEN):
                return urllib.request.urlopen(urllib.request.Request(url,data=json.dumps(data).encode() if data is not None else None,headers={'Authorization':'Bearer '+token,'Content-Type':'application/json'}))
            try:
                with self.assertRaises(urllib.error.HTTPError) as denied: request(token='wrong')
                self.assertEqual(denied.exception.code,401)
                data = dict(host='Aina',start='2026-10-16T22:00',end='2026-10-17T01:00',gmv='123.45',views='1200',notes='<test>')
                self.assertEqual(request(data).status,201)
                server.initialize()
                rows=json.load(request());self.assertEqual(rows[0]['gmv_cents'],12345);self.assertEqual(rows[0]['views'],1200)
                for bad in [dict(data,gmv='NaN'),dict(data,views='1.5'),dict(data,end=data['start']),dict(data,host='')]:
                    with self.assertRaises(urllib.error.HTTPError) as error: request(bad)
                    self.assertEqual(error.exception.code,400)
                self.assertEqual(len(json.load(request())),1)
            finally:
                http.shutdown(); http.server_close()

if __name__=='__main__': unittest.main()
