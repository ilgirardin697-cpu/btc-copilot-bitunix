"""Explicit standalone PAPER entry point; import never starts a worker."""
import argparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import html
import json
from pathlib import Path
import socket
import threading
import time

from .service import Service, environment_guard


def handler(directory):
    class ReadOnlyReport(BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass

        def do_GET(self):
            if self.path == '/health':
                body, mime = b'{"alive":true,"mode":"PAPER_ONLY","trade_authority":"NONE"}', 'application/json'
            elif self.path in ('/', '/report.md', '/report.json'):
                name = 'report.json' if self.path == '/report.json' else 'report.md'
                path = Path(directory) / name
                if not path.exists():
                    self.send_error(503, 'Paper report initializing')
                    return
                body = path.read_bytes()
                mime = 'application/json' if name.endswith('.json') else 'text/plain; charset=utf-8'
                if self.path == '/':
                    body = ('<!doctype html><meta charset="utf-8"><meta http-equiv="refresh" content="60"><title>I-GOD PAPER</title><style>body{max-width:1100px;margin:2rem auto;background:#101827;color:#e2e8f0;font:15px monospace}pre{white-space:pre-wrap}</style><h1>I-GOD — PAPER ONLY</h1><p>SHADOW ONLY · TRADE AUTHORITY: NONE</p><a href="/report.json">JSON</a> · <a href="/report.md">Informe</a><pre>' + html.escape(body.decode('utf-8')) + '</pre>').encode('utf-8')
                    mime = 'text/html; charset=utf-8'
            else:
                self.send_error(404)
                return
            self.send_response(200)
            self.send_header('Content-Type', mime)
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_POST(self):
            self.send_error(405)

        do_PUT = do_DELETE = do_PATCH = do_POST
    return ReadOnlyReport


def main():
    parser = argparse.ArgumentParser(description='Standalone I-GOD paper simulation; never live execution')
    parser.add_argument('--directory', required=True)
    parser.add_argument('--serve', action='store_true', help='Continuously poll public data and serve private read-only reports')
    args = parser.parse_args()
    import os
    environment_guard(os.environ)
    service = Service(args.directory)
    server = None
    if args.serve:
        class DualStackReportServer(ThreadingHTTPServer):
            address_family = socket.AF_INET6

            def server_bind(self):
                self.socket.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_V6ONLY, 0)
                super().server_bind()

        server = DualStackReportServer(('::', 8080), handler(args.directory))
        threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        while True:
            report = service.cycle()
            if not args.serve:
                return 0 if report['status'] == 'HEALTHY' else 1
            time.sleep(30)
    finally:
        if server:
            server.shutdown()
        service.journal.close()


if __name__ == '__main__':
    raise SystemExit(main())
