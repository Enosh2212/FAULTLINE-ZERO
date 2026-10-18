from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from urllib.request import Request, build_opener, HTTPRedirectHandler
from urllib.error import HTTPError
from urllib.parse import urlsplit
from pathlib import Path
class NoRedirect(HTTPRedirectHandler):
 def redirect_request(self, req, fp, code, msg, headers, newurl): return None
OPENER=build_opener(NoRedirect)
ROOT=Path(__file__).resolve().parents[1]/'src/faultline/web'
class Handler(SimpleHTTPRequestHandler):
 def do_GET(self):
  if self.path.startswith('/api/') or urlsplit(self.path).path == '/workspace': return self.proxy()
  if urlsplit(self.path).path in ('/login','/register'): self.path='/auth.html'
  self.path=self.path.replace('/assets/','/',1)
  return super().do_GET()
 def do_POST(self): self.proxy()
 def proxy(self):
  data=self.rfile.read(int(self.headers.get('Content-Length',0))) if self.command=='POST' else None
  headers={k:v for k,v in self.headers.items() if k.lower() in ('authorization','content-type','cookie','x-csrf-token','origin')}
  try:
   with OPENER.open(Request('http://127.0.0.1:8000'+self.path,data=data,headers=headers,method=self.command),timeout=180) as r:
    self.send_response(r.status);self.send_header('Content-Type',r.headers.get('Content-Type','application/json'))
    for cookie in r.headers.get_all('Set-Cookie',[]): self.send_header('Set-Cookie',cookie)
    self.send_header('Cache-Control','no-store');self.end_headers();self.wfile.write(r.read())
  except HTTPError as e:
   self.send_response(e.code);self.send_header('Content-Type',e.headers.get('Content-Type','application/json'))
   if e.headers.get('Location'): self.send_header('Location',e.headers['Location'])
   self.send_header('Cache-Control','no-store');self.end_headers();self.wfile.write(e.read())
  except Exception as e:
   self.send_error(getattr(e,'code',502),str(e))
 def __init__(self,*a,**kw): super().__init__(*a,directory=str(ROOT),**kw)
ThreadingHTTPServer(('127.0.0.1',8001),Handler).serve_forever()
