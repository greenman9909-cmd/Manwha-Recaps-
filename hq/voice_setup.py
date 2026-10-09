"""Private one-time Google AI Studio key setup on the laptop only.

NO key in ChatGPT, command line, URL, server logs, or analytics.
Binds localhost only; validates key using model-list GET before storing
under ~/.flow-mcp/gemini-key with Windows user-only ACL.
Never generates audio or uses paid TTS requests during configuration.
"""
from __future__ import annotations
from html import escape
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import os
from pathlib import Path
import secrets
import sys
import threading
from urllib.parse import parse_qs

ROOT = Path(r"D:\AshenToons")
sys.path.insert(0, str(ROOT / "studio-code"))
from ashentoons.gemini_tts import credential_ready, save_key_securely  # noqa

PORT = 8771
HOST = "127.0.0.1"
FORM_TOKEN = secrets.token_urlsafe(32)

HTML = """<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>AshenToons — Google Voice Setup</title>
<style>
*{box-sizing:border-box}
body{margin:0;background:#0b111b;color:#e9eefe;font:15px "Segoe UI",system-ui,sans-serif;display:grid;place-items:center;min-height:100vh;padding:16px}
main{width:min(560px,100%);background:#152034;border:1px solid #38455c;padding:28px;border-radius:22px;box-shadow:0 20px 60px #0006}
.pill{display:inline-block;border-radius:15px;background:#293757;color:#baabfc;font-size:11px;letter-spacing:.09em;font-weight:800;padding:7px 10px}
h1{font-size:28px;margin:16px 0 8px}p{color:#a8b7ca;line-height:1.6}
strong{color:#eef2fb}label{display:block;margin:22px 0 8px;font-weight:800;font-size:12px}
input[type=password]{display:block;width:100%;border-radius:12px;background:#0d1724;border:1px solid #52617b;padding:15px;color:#fff;font-size:17px;outline:0}
input:focus{border-color:#b39cff}
button{padding:13px 18px;background:#a48ef0;border:0;border-radius:10px;font-weight:800;color:#1b1537;cursor:pointer;margin-top:17px;width:100%}
.note{border-radius:11px;background:#202d43;padding:13px;margin-top:17px;color:#b9c7da;font-size:12px}
.ok{background:#163e33;color:#9de4c4;border:1px solid #326756}
.error{background:#452c32;color:#ffadb3;border:1px solid #74414b}
small{color:#8999b0;font-size:12px}
a{color:#c7b2ff}
</style></head><body><main><span class="pill">ASHENTOONS · PRIVATE VOICE SETUP</span>
<h1>Google AI Studio voices</h1>
<p>Connect your API key locally. The key is verified with Google's <strong>read-only model listing</strong> and stored with your Windows account's file permissions. No audio generation or Flow credits are spent here.</p>
{{MESSAGE}}
{{FORM}}
<div class="note"><strong>Important:</strong> Your Google AI Plus subscription doesn't automatically pay for Gemini API requests. Generating TTS later is an optional action that may incur API charges. Kokoro Fenrir remains our default narrator.</div>
<p style="font-size:12px">Don't paste the key into ChatGPT. The connection is <strong>127.0.0.1</strong>, only on this laptop. Existing <code>flow-mcp</code> can reuse the same local key file.</p>
</main></body></html>"""


def page(message="", include_form=True):
    if credential_ready():
        status='<div class="note ok">✓ Google API key is configured on this laptop.</div>'
    else:
        status='<div class="note">No Google voice API key is configured yet.</div>'
    if message:
        status += '<div class="note '+("error" if "failed" in message.lower() or "invalid" in message.lower() or "could not" in message.lower() else "ok")+'">'+escape(message)+'</div>'
    form=(
        '<form action="/configure" method="post" autocomplete="off">'
        '<input type="hidden" name="csrf" value="'+FORM_TOKEN+'">'
        '<label for="api-key">Google AI Studio API key</label>'
        '<input id="api-key" type="password" name="key" autofocus required autocomplete="off"'
        ' pattern="[A-Za-z0-9_.-]{20,256}" minlength="20" maxlength="256" placeholder="Paste a freshly rotated API key here (never into chat)">'
        '<button type="submit">Validate and save privately →</button>'
        '</form>'
    ) if include_form else '<p>You can close this tab. The secure setup server will stop.</p>'
    return HTML.replace("{{MESSAGE}}",status).replace("{{FORM}}",form).encode("utf-8")


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args): pass

    def send_page(self, html, status=200):
        self.send_response(status)
        self.send_header("Content-Type","text/html; charset=utf-8")
        self.send_header("Content-Length",str(len(html)))
        self.send_header("Cache-Control","no-store")
        self.send_header("Referrer-Policy","no-referrer")
        self.send_header("X-Frame-Options","DENY")
        self.send_header("X-Content-Type-Options","nosniff")
        self.send_header("Content-Security-Policy","default-src 'none'; style-src 'unsafe-inline'; form-action 'self'; base-uri 'none'; frame-ancestors 'none'")
        self.end_headers()
        self.wfile.write(html)

    def do_GET(self):
        if self.path not in ("/","/index.html","/configure"):
            self.send_error(404);return
        self.send_page(page())

    def do_POST(self):
        if self.path != "/configure":
            self.send_error(404);return
        # Some Windows browsers/privacy modes omit or rewrite Origin for a
        # loopback form. Bind to 127.0.0.1 and validate Host instead; the
        # unpredictable per-process CSRF token below remains mandatory.
        # This prevents DNS rebinding while allowing genuine local browsers.
        requested_host = self.headers.get("Host", "").lower()
        if requested_host not in {f"127.0.0.1:{PORT}", f"localhost:{PORT}"}:
            self.send_page(page("Open this form at http://127.0.0.1:8771/ on this laptop"),403)
            return
        try:
            size = int(self.headers.get("Content-Length","0"))
            if not 1 <= size <= 1024: raise ValueError("Unexpected request size")
            form = parse_qs(self.rfile.read(size).decode("utf-8"),keep_blank_values=True)
            csrf = form.get("csrf",[""])[0]
            raw_key=form.get("key",[""])[0]
            if not secrets.compare_digest(csrf,FORM_TOKEN):
                self.send_page(page("Invalid setup token"),403);return
            result=save_key_securely(raw_key)
            # Never echo or log the submitted key.
            if result["status"] == "PASS":
                self.send_page(page("Google voice key configured securely. No API audio generated.",False))
                threading.Thread(target=self.server.shutdown,daemon=True).start()
            else:
                self.send_page(page(result["message"]),400)
        except (UnicodeError,ValueError,TypeError):
            self.send_page(page("Invalid setup request"),400)


if __name__ == "__main__":
    print(f"SECURE_VOICE_SETUP=http://{HOST}:{PORT}/", flush=True)
    print("SCOPE=THIS_LAPTOP_ONLY KEY_VISIBILITY=NEVER AUDIO_REQUESTS=ZERO",flush=True)
    ThreadingHTTPServer((HOST,PORT), Handler).serve_forever()
