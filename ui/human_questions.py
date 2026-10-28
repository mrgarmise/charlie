"""Loopback-only question service. Use an authenticated SSH tunnel for LAN use.

The operator name comes from server configuration, never an answer payload.
There is no evidence submission endpoint, arbitrary file route or hardware import.
"""
import argparse
import hmac
import html
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
import os
from pathlib import Path
import secrets
from urllib.parse import parse_qs, urlsplit

from memory.evidence import EvidenceJournal
from memory.human_interaction import HumanInteractionGateway, TYPES


def page(service, csrf):
    esc = lambda x: html.escape(str(x), quote=True)
    cards = []
    for q in reversed(list(service.questions().values())):
        n = q['need']
        choices = ''.join('<option value="'+esc(v)+'">'+esc(v)+'</option>' for v in n['candidates'])
        form = ''
        if q['status'] in ('pending', 'failed'):
            form = f'''<form method="post" action="/answer">
<input type="hidden" name="csrf" value="{esc(csrf)}">
<input type="hidden" name="question_id" value="{esc(q['id'])}">
<input type="hidden" name="request_id" value="{secrets.token_hex(16)}">
<label>Answer <select name="value"><option value="">I don't know</option>{choices}</select></label>
<label>Explanation (optional)<textarea name="explanation" maxlength="2048"></textarea></label>
<button>Save answer for review</button></form>'''
        cards.append(f'''<article data-priority="{q['urgency']}"><p>{esc(q['status'])} · priority {q['urgency']} · {esc(n['owner'])}</p>
<h2>{esc(TYPES[n['kind']])}</h2><p>{esc(n['proposition'])}</p><p>Why: {esc(n['reason'])}</p>
<p>Evidence confidence: {esc(n['confidence'])} (source-reported; not truth)</p>
<details><summary>Evidence and history</summary><pre>{esc(json.dumps(q, indent=2))}</pre></details>{form}</article>''')
    return ('''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Charlie's questions</title><style>body{font:17px system-ui;background:#eef3f4;color:#19343d;max-width:850px;margin: auto;padding:20px}article{background:white;border-radius:16px;padding:20px;margin:20px 0}label{display:block;margin:12px 0}select,textarea,button{font:inherit;width:100%;box-sizing:border-box;padding:12px}button{background:#1a6264;color:white;border:0;border-radius:8px}pre{white-space:pre-wrap;overflow-wrap:anywhere}h2{font-size:1.3rem}</style>
<h1>Charlie's questions</h1><p>A quiet backlog. Answer whenever convenient. Human replies are fallible evidence for review; they grant no movement or model authority.</p>'''
        + ''.join(cards or ['<p>No questions waiting.</p>']) + '</html>').encode()


def handler_factory(service, token, operator, port):
    if len(token) < 32 or not operator.strip():
        raise ValueError('32-character secret and operator identity required')
    csrf = secrets.token_urlsafe(32)
    host = '127.0.0.1:'+str(port)

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass  # Never log credentials, answers or camera context.

        def send(self, status, body=b'', content_type='text/plain; charset=utf-8'):
            self.send_response(status)
            self.send_header('Content-Type', content_type)
            self.send_header('Content-Length', str(len(body)))
            self.send_header('Cache-Control', 'no-store')
            self.send_header('Content-Security-Policy', "default-src 'none'; style-src 'unsafe-inline'; form-action 'self'; frame-ancestors 'none'; base-uri 'none'")
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.end_headers()
            self.wfile.write(body)

        def authorized(self):
            # Basic auth works in native mobile browsers without JS or URL secrets.
            import base64
            expected = 'Basic '+base64.b64encode(('operator:'+token).encode()).decode()
            if self.headers.get('Host') != host:
                self.send(403); return False
            if not hmac.compare_digest(self.headers.get('Authorization', ''), expected):
                self.send_response(401)
                self.send_header('WWW-Authenticate', 'Basic realm="Charlie questions"')
                self.send_header('Content-Length', '0')
                self.end_headers(); return False
            return True

        def do_GET(self):
            if not self.authorized(): return
            if self.path == '/':
                self.send(200, page(service, csrf), 'text/html; charset=utf-8')
            elif self.path == '/api/questions':
                self.send(200, json.dumps(service.questions()).encode(), 'application/json')
            else:
                self.send(404)

        def do_POST(self):
            if not self.authorized(): return
            if self.path != '/answer':
                self.send(404); return
            if (self.headers.get('Origin') not in (None, 'http://'+host)
                    or self.headers.get('Sec-Fetch-Site') not in (None, 'same-origin', 'none')):
                self.send(403); return
            if self.headers.get('Content-Type') != 'application/x-www-form-urlencoded' or self.headers.get('Transfer-Encoding'):
                self.send(415); return
            try:
                length = int(self.headers.get('Content-Length', '0'))
                if not 0 < length <= 16384:
                    self.send(413); return
                data = parse_qs(self.rfile.read(length).decode('utf-8'), keep_blank_values=True, max_num_fields=8)
                if set(data) != {'csrf', 'question_id', 'request_id', 'value', 'explanation'} or any(len(v) != 1 for v in data.values()):
                    raise ValueError('invalid form')
                data = {k:v[0] for k,v in data.items()}
                if not hmac.compare_digest(data.pop('csrf'), csrf):
                    self.send(403); return
                service.answer(data['question_id'], value=data['value'] or None,
                    explanation=data['explanation'], operator=operator, request_id=data['request_id'])
            except (ValueError, KeyError, UnicodeError):
                self.send(400, b'Invalid or closed question; reload to inspect status.'); return
            except Exception:
                self.send(503, b'Not committed; retry with the same request ID.'); return
            self.send(200, page(service, csrf), 'text/html; charset=utf-8')

    return Handler


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--journal', type=Path, required=True)
    parser.add_argument('--operator', required=True)
    parser.add_argument('--port', type=int, default=8787)
    args = parser.parse_args()
    token = os.environ.get('CHARLIE_QUESTIONS_TOKEN', '')
    if len(token) < 32 or not 1024 <= args.port <= 65535:
        parser.error('set CHARLIE_QUESTIONS_TOKEN to a secret of at least 32 characters; port 1024..65535')
    journal = EvidenceJournal(args.journal)
    service = HumanInteractionGateway(journal)
    server = HTTPServer(('127.0.0.1', args.port), handler_factory(service, token, args.operator, args.port))
    server.timeout = 1
    # Bound slow clients too; service is deliberately single-threaded with one SQLite owner.
    original = server.get_request
    def accept():
        sock, addr = original(); sock.settimeout(5); return sock, addr
    server.get_request = accept
    print(f'Questions: http://127.0.0.1:{args.port}/ (Ctrl-C to stop)')
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close(); journal.close()


if __name__ == '__main__':
    main()
