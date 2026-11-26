"""Authenticated private event ingress. No poller, orders or arbitrary URL proxy."""
import hashlib
import hmac
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
import json
import socket
import threading


def signature(key,body):
    return hmac.new(key.encode(),body,hashlib.sha256).hexdigest()


def handler(host,key):
    class Handler(BaseHTTPRequestHandler):
        def setup(self):
            super().setup();self.connection.settimeout(3)
        def log_message(self,*args):pass
        def reply(self,status,value):
            raw=json.dumps(value,separators=(',',':')).encode()
            self.send_response(status);self.send_header('Content-Type','application/json')
            self.send_header('Content-Length',str(len(raw)));self.end_headers();self.wfile.write(raw)
        def do_GET(self):
            if self.path!='/health':return self.reply(404,{'ok':False})
            return self.reply(200 if host.ready.is_set() and not host.failed else 503,{'ok':host.ready.is_set() and not host.failed})
        def do_POST(self):
            if self.path!='/events':return self.reply(404,{'ok':False})
            try:
                size=int(self.headers.get('Content-Length','0'))
                if not 0<size<=16000:return self.reply(413,{'ok':False})
                if self.headers.get('Content-Type','').split(';')[0]!='application/json':return self.reply(415,{'ok':False})
                body=self.rfile.read(size)
                auth=self.headers.get('X-IGOD-Signature','')
                if not hmac.compare_digest(auth,signature(key,body)):return self.reply(401,{'ok':False})
                value=json.loads(body)
                if not isinstance(value,dict):return self.reply(400,{'ok':False})
                if value.get('source')!='v8' or value.get('kind') not in ('OBSERVATION','CRITICAL','RECOVERED'):
                    return self.reply(403,{'ok':False})
                result=host.rpc('event',value)
                return self.reply(200,dict(ok=True,record_id=value['id'],**result))
            except (ValueError,TypeError,KeyError,json.JSONDecodeError):return self.reply(400,{'ok':False})
            except Exception:return self.reply(503,{'ok':False})
        def do_PUT(self):return self.reply(405,{'ok':False})
        def do_DELETE(self):return self.reply(405,{'ok':False})
    return Handler


def start(host,key):
    class DualStack(ThreadingHTTPServer):
        address_family=socket.AF_INET6
        daemon_threads=True
        request_queue_size=8
        slots=threading.BoundedSemaphore(16)
        def verify_request(self,request,client_address):return self.slots.acquire(blocking=False)
        def process_request_thread(self,request,client_address):
            try:super().process_request_thread(request,client_address)
            finally:self.slots.release()
        def server_bind(self):
            self.socket.setsockopt(socket.IPPROTO_IPV6,socket.IPV6_V6ONLY,0)
            super().server_bind()
    server=DualStack(('::',8091),handler(host,key))
    threading.Thread(target=server.serve_forever,daemon=True,name='igod-notification-private-ingress').start()
    return server
