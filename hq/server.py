"""AshenToons HQ: a persistent, evidence-based local production control room.

One real GPT-6 creative intelligence can read and post through bridge.py while
connected to ChatGPT Desktop Commander. Department personalities are documented
roles and deterministic verification workers, NEVER impersonated API agents.
No code downloads, public uploads, destructive shell actions, or AI impersonation.
"""
from __future__ import annotations
import argparse
from contextlib import contextmanager
import ipaddress
import json
import os
from pathlib import Path
import re
import secrets
import sqlite3
import subprocess
import threading
import time
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit
import wave

ROOT = Path(r"D:\AshenToons")
STUDIO = ROOT / "control-room"
PROJECT = ROOT / "projects" / "healing-magic-001"
REPO = ROOT / "studio-code"
EXTERNAL_EDITOR = Path(r"C:\Users\green\Documents\GPT6-Video-Editor-Standalone")
PORT = 8770
BIND = "0.0.0.0"
DB = STUDIO / "studio.sqlite3"
STATIC = STUDIO / "static"
AVATARS = STUDIO / "avatars"
LOGS = STUDIO / "logs"
PLANS = STUDIO / "plans"
SECRET = STUDIO / "secrets" / "access-token.txt"
LOCK = threading.RLock()
ACTIVE: set[str] = set()

DEPARTMENTS = [
    dict(id="ceo", name="Astra", title="CEO · GPT-6", tone="Strategic, demanding, protective of story quality. Delegates decisively.", motto="Evidence before applause.", color="#8a6cf1", kind="gpt6", marker="CEO"),
    dict(id="operator", name="Forge", title="Production Operator · GPT-6", tone="Hands-on, methodical, resourceful. Repairs problems instead of theorizing.", motto="Show the file, not a promise.", color="#3dbcc5", kind="gpt6", marker="OPS"),
    dict(id="management", name="Mira", title="Production Manager", tone="Tactically precise and organized; gives concise honest status reports.", motto="Every blocker gets an owner.", color="#cf92f9", kind="worker", marker="PM"),
    dict(id="story", name="Ren", title="Story Director", tone="Canon-obsessed storyteller with dry humor; won't invent dialogue.", motto="The panel must prove the line.", color="#f1ad68", kind="worker", marker="STORY"),
    dict(id="source", name="Atlas", title="Panel & Source Lead", tone="Forensic archivist; protects source integrity, order and provenance.", motto="Right chapter. Right order.", color="#8bb9fd", kind="worker", marker="SOURCE"),
    dict(id="audio", name="Echo", title="Voice Director", tone="Expressive perfectionist; checks cast consistency, audio format and delivery.", motto="A character must sound like themselves.", color="#69d5ae", kind="worker", marker="VOICE"),
    dict(id="editing", name="Kairo", title="Lead Video Editor", tone="Cinematic and impatient with sluggish cuts; respects original panels.", motto="Every cut earns its place.", color="#ff8b75", kind="worker", marker="EDIT"),
    dict(id="qa", name="Iris", title="Independent QA Lead", tone="Skeptical, precise, refuses unsupported PASS claims.", motto="Decodable isn't the same as correct.", color="#f2c45f", kind="worker", marker="QA"),
    dict(id="thumbnail", name="Nova", title="Art & SEO Director", tone="Bold visual taste; real manga panels and concise curiosity hooks.", motto="Make it irresistible, never misleading.", color="#ee7bab", kind="worker", marker="ART"),
    dict(id="publishing", name="Vale", title="Release Manager", tone="Measured gatekeeper; no accidental public uploads.", motto="Nothing ships unreviewed.", color="#a5a9c4", kind="worker", marker="SHIP"),
]
BY_ID = {d["id"]: d for d in DEPARTMENTS}
ACTIONS = {
    "readiness": ("Management · Production readiness", "management"),
    "test-studio": ("Engineering · AshenToons tests", "operator"),
    "audit-cast": ("Echo · Five-voice audition audit", "audio"),
    "scan-sources": ("Atlas · Manga source verification", "source"),
    "audit-editor": ("Kairo · Standalone editor doctor", "editing"),
    "create-plan": ("Mira · Episode execution plan", "management"),
    "review-gates": ("Iris · Independent release gates", "qa"),
}
TASK_ROWS = [
    ("source", "Import original manga chapters", "Manga Sources"),
    ("story", "Create panel-locked story script", "Story & Script"),
    ("audio", "Produce consistent character voices", "Voice & Casting"),
    ("editing", "Build 60-minute narrated feature", "Editing & Motion"),
    ("qa", "Verify every chapter's A/V alignment", "Independent QA"),
    ("thumbnail", "Real-panel thumbnail and SEO", "Art & Growth"),
    ("publishing", "Private review and release gate", "Distribution"),
]

def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")

@contextmanager
def db_open():
    """Always close SQLite connections (especially on Windows)."""
    db = sqlite3.connect(DB, timeout=15)
    try:
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA busy_timeout=15000")
        with db:
            yield db
    finally:
        db.close()

def initialize():
    for path in (STUDIO, STATIC, AVATARS, LOGS, PLANS, SECRET.parent):
        path.mkdir(parents=True, exist_ok=True)
    if not SECRET.exists():
        with SECRET.open("x", encoding="utf8") as out:
            out.write(secrets.token_urlsafe(32))
    with LOCK, db_open() as db:
        db.execute("PRAGMA journal_mode=WAL")
        db.executescript("""
        CREATE TABLE IF NOT EXISTS messages (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          channel TEXT NOT NULL DEFAULT 'group',
          role TEXT NOT NULL,
          origin TEXT NOT NULL,
          body TEXT NOT NULL,
          ts TEXT NOT NULL,
          evidence TEXT
        );
        CREATE TABLE IF NOT EXISTS tasks (
          id TEXT PRIMARY KEY,
          title TEXT NOT NULL,
          department TEXT NOT NULL,
          status TEXT NOT NULL,
          progress INTEGER NOT NULL DEFAULT 0,
          note TEXT NOT NULL DEFAULT '',
          evidence TEXT,
          ts TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS jobs (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          action TEXT NOT NULL,
          status TEXT NOT NULL,
          started TEXT NOT NULL,
          ended TEXT,
          result TEXT
        );
        CREATE TABLE IF NOT EXISTS inbox (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          channel TEXT NOT NULL,
          body TEXT NOT NULL,
          status TEXT NOT NULL DEFAULT 'pending',
          ts TEXT NOT NULL
        );
        """)
        for key,title,group in TASK_ROWS:
            db.execute("INSERT OR IGNORE INTO tasks(id,title,department,status,note,ts) VALUES(?,?,?,?,?,?)",
                       (key,title,group,"waiting","Needs verified project evidence",now()))
        if not db.execute("SELECT 1 FROM messages LIMIT 1").fetchone():
            db.execute("INSERT INTO messages(channel,role,origin,body,ts) VALUES(?,?,?,?,?)",
                       ("group","ceo","gpt6","AshenToons HQ is open. GPT-6 directs the studio; local departments execute verified checks. No fabricated progress, no artificial manga artwork, no upload without approval.",now()))
            db.execute("INSERT INTO messages(channel,role,origin,body,ts) VALUES(?,?,?,?,?)",
                       ("group","management","system","Production tracker online. We will record real outputs, blocking dependencies and evidence—not empty status updates.",now()))
        db.commit()

def add_message(role, body, origin="worker", channel="group", evidence=None):
    if role not in BY_ID and role!="you":
        raise ValueError("Unknown sender")
    if origin not in ("gpt6","worker","system","user","local_ai"):
        raise ValueError("Unknown origin")
    body=str(body).strip()
    if not body or len(body)>6000:
        raise ValueError("Invalid message body")
    if channel!="group" and channel not in BY_ID:
        raise ValueError("Unknown channel")
    with LOCK,db_open() as db:
        cur=db.execute("INSERT INTO messages(channel,role,origin,body,ts,evidence) VALUES(?,?,?,?,?,?)",
                       (channel,role,origin,body,now(),evidence))
        db.commit()
        return cur.lastrowid

def update_task(key, status, progress, note, evidence=None):
    if key not in {t[0] for t in TASK_ROWS}:
        return
    if status not in ("ready","active","blocked","waiting","review"):
        raise ValueError("Invalid task status")
    with LOCK,db_open() as db:
        db.execute("UPDATE tasks SET status=?,progress=?,note=?,evidence=?,ts=? WHERE id=?",
                   (status,max(0,min(100,int(progress))),str(note)[:450],evidence,now(),key))
        db.commit()

def inspector():
    result={"project":"The Wrong Way to Use Healing Magic", "episode":"healing-magic-001"}
    config=PROJECT/"production.json"
    try: conf=json.loads(config.read_text(encoding="utf8")) if config.is_file() else {}
    except (OSError,ValueError):conf={}
    result["voice_map"]=conf.get("voices",{})
    result["mc_voice"]=result["voice_map"].get("MC")
    wavs={}
    for speaker in ("mc","usato","rose","suzune","kazuki"):
        for file in (PROJECT/"auditions").glob("*-"+speaker+"-*.wav"):
            try:
                with wave.open(str(file),"rb") as w:
                    wavs[speaker]={"path":str(file),"duration":round(w.getnframes()/w.getframerate(),2),
                                   "sample_rate":w.getframerate(),"channels":w.getnchannels()}
            except (OSError,wave.Error,ZeroDivisionError):
                pass
    result["auditions"]=wavs
    result["cast_ready"]=len(wavs)==5 and all(v["sample_rate"]==24000 for v in wavs.values()) and result["mc_voice"]=="am_fenrir"
    sources=ROOT/"sources"/"healing-magic"
    chapters=[]
    if sources.is_dir():
        for folder in sorted(sources.iterdir()):
            if not folder.is_dir() or not re.fullmatch(r"ch\d{3,5}",folder.name):
                continue
            files=[p for p in folder.iterdir() if p.is_file() and p.suffix.lower() in (".png",".jpg",".jpeg",".webp")]
            if files:
                ledger=ROOT/"manifests"/"healing-magic"/f"chapter-{int(folder.name[2:]):03d}-source.json"
                chapters.append({"chapter":folder.name,"pages":len(files),"provenance":ledger.is_file()})
    result["chapters"]=chapters
    result["sources_ready"]=bool(chapters) and all(c["provenance"] for c in chapters)
    manifests=ROOT/"manifests"/"healing-magic"
    result["story_scripts"]=sorted(p.name for p in manifests.glob("*script*.json")) if manifests.is_dir() else []
    result["script_ready"]=result["sources_ready"] and len(result["story_scripts"])>0
    exports=ROOT/"exports"/"healing-magic-001"
    result["videos"]=[{"file":p.name,"bytes":p.stat().st_size} for p in exports.glob("*.mp4") if p.is_file() and p.stat().st_size>1000000] if exports.is_dir() else []
    try:
        git=subprocess.run(["git","-C",str(REPO),"rev-parse","--short","HEAD"],
                           timeout=7,capture_output=True,text=True)
        result["studio_revision"]=git.stdout.strip() if git.returncode==0 else None
    except (OSError,subprocess.TimeoutExpired):result["studio_revision"]=None
    result["standalone_editor_installed"]=(EXTERNAL_EDITOR/"editor.ps1").is_file()
    result["art_ready"]=False
    return result

def refresh_status(h=None):
    h=h or inspector()
    update_task("source","ready" if h["sources_ready"] else "blocked",100 if h["sources_ready"] else 0,
                f"{len(h['chapters'])} chapter(s) with provenance" if h["sources_ready"] else "No imported, ledger-backed Healing Magic chapter pages")
    update_task("story","review" if h["script_ready"] else "blocked",55 if h["script_ready"] else 0,
                "Script candidate exists; still needs semantic review" if h["script_ready"] else "Requires real panels before scene-by-scene narration")
    update_task("audio","ready" if h["cast_ready"] else "blocked",100 if h["cast_ready"] else 0,
                f"{len(h['auditions'])}/5 verified Kokoro auditions; MC am_fenrir" if h["cast_ready"] else "Cast samples or MC voice incomplete")
    update_task("editing","review" if h["videos"] else "waiting",55 if h["videos"] else 0,
                "Video candidate exists; verify timeline" if h["videos"] else "Render waits on panels, reviewed script and timed narration")
    update_task("qa","waiting",0,"Technical checks are not evidence of panel-dialogue accuracy")
    update_task("thumbnail","waiting",0,"Use only authorized original manga panels; no AI-generated art")
    update_task("publishing","waiting",0,"No reviewed final master; no public upload")
    return h

def safe_run(args, cwd=None, timeout=120, extra=None):
    environment=os.environ.copy()
    environment["PYTHONUTF8"]="1"
    environment["PYTHONIOENCODING"]="utf-8"
    if extra:environment.update(extra)
    p=subprocess.run(args,cwd=cwd,capture_output=True,text=True,errors="replace",timeout=timeout,env=environment)
    return p.returncode,(p.stdout+"\n"+p.stderr)[-24000:]

def execute(action):
    if action=="readiness":
        h=refresh_status()
        add_message("management",
                    f"Verified project: AshenToons {h['studio_revision']}; {len(h['chapters'])} imported chapters; "
                    f"{len(h['auditions'])}/5 audition voices; {len(h['story_scripts'])} story scripts; "
                    f"{len(h['videos'])} rendered Healing Magic MP4s. "
                    "Full-video readiness: NO until sources, story mapping and visual QC pass.",
                    evidence=str(PROJECT/"production.json"))
        add_message("source","Chapter sources: "+
                    ("present, provenance recorded, editor review pending." if h["sources_ready"]
                     else "BLOCKED — no locally imported Healing Magic panels in D:\\AshenToons\\sources\\healing-magic."))
        add_message("audio",f"Cast {'READY' if h['cast_ready'] else 'BLOCKED'}: MC voice is {h['mc_voice']}; "
                    f"{len(h['auditions'])} real WAV auditions found.")
        add_message("qa","Independent QA: not yet approved. A passing code test cannot verify dialogue against manga pages.")
        return {"ok":True,"health":h}
    if action=="test-studio":
        executable=str(ROOT/"tools"/".venv-memanga"/"Scripts"/"python.exe")
        if not Path(executable).is_file():
            raise RuntimeError("Known Python 3.11 studio environment missing")
        rc,out=safe_run([executable,"-m","unittest","discover","-s","tests","-q"],
                        cwd=str(REPO),timeout=150,extra={"PYTHONPATH":str(REPO)})
        file=LOGS/f"studio-tests-{int(time.time())}.txt"
        file.write_text(out,encoding="utf8")
        match=re.search(r"Ran (\d+) tests",out)
        count=match.group(1) if match else "unknown"
        passed=rc==0 and re.search(r"\nOK\s*(?:\(|\n|$)",out) is not None
        add_message("operator",f"Studio test run {'PASS' if passed else 'FAIL'}: "
                    f"{count} tests. Log: {file.name}. This is code QC, not story QC.",
                    evidence=str(file))
        return {"ok":passed,"test_count":count,"log":str(file),"exit_code":rc}
    if action=="audit-cast":
        h=refresh_status()
        cast=h["auditions"]
        result=f"Checked {len(cast)}/5 WAV samples, 24kHz target. Narrator: {h['mc_voice']}."
        add_message("audio",result+
                    (" Casting ready; no episode dialogue recorded." if h["cast_ready"]
                     else " Some samples are missing or wrong format."),
                    evidence=str(PROJECT/"production.json"))
        return {"ok":h["cast_ready"],"auditions":cast,"voice_map":h["voice_map"]}
    if action=="scan-sources":
        h=refresh_status()
        add_message("source",f"Source scan complete: {len(h['chapters'])} imported chapters. "
                    +("Ledger evidence found; start panel-level reading order review."
                      if h["sources_ready"] else
                      "Cannot begin faithful scene mapping without genuine imported pages."),
                    evidence=str(ROOT/"sources"/"healing-magic"))
        return {"ok":h["sources_ready"],"chapters":h["chapters"]}
    if action=="audit-editor":
        script=EXTERNAL_EDITOR/"editor.ps1"
        if not script.is_file():raise RuntimeError("Standalone editor not found")
        rc,out=safe_run(["powershell.exe","-NoProfile","-ExecutionPolicy","Bypass","-File",str(script),"doctor"],
                        cwd=str(EXTERNAL_EDITOR),timeout=35)
        try:check=json.loads(out.strip())
        except (ValueError,TypeError):check={"raw_excerpt":out[-1000:]}
        passed=rc==0 and check.get("hyperframes") is True and check.get("playwright") is True
        log=LOGS/f"editor-doctor-{int(time.time())}.txt"
        log.write_text(out,encoding="utf8")
        add_message("editing",f"Standalone editor {'AVAILABLE' if passed else 'NEEDS FIX'}: "
                    "HyperFrames / Playwright / FFmpeg checked without changing the standalone editor. "
                    "Its workspace remains isolated.",
                    evidence=str(log))
        return {"ok":passed,"check":check,"log":str(log)}
    if action=="create-plan":
        target=PLANS/"healing-magic-episode-plan.json"
        if target.exists():
            result=json.loads(target.read_text("utf8"))
            add_message("management","Episode execution plan already exists; reused unchanged.",evidence=str(target))
            return {"ok":True,"reused":True,"path":str(target),"milestones":len(result["milestones"])}
        config=PROJECT/"production.json"
        existing=json.loads(config.read_text("utf8")) if config.is_file() else {}
        plan={
            "series":"The Wrong Way to Use Healing Magic",
            "project_id":"healing-magic-001",
            "lead_model":"GPT-6 in connected ChatGPT; NOT an unattended local GPT-6 service",
            "director_role":"ceo",
            "operator_role":"operator",
            "source_authorization":"User confirmed for this project",
            "source_format":"Japanese manga, right-to-left panel reading",
            "source_dir":str(ROOT/"sources"/"healing-magic"),
            "audio_dir":str(PROJECT/"auditions"),
            "narrator_voice":existing.get("voices",{}).get("MC","am_fenrir"),
            "cast":existing.get("voices",{}),
            "target_minutes":60,
            "added_subtitles":False,
            "ai_generated_manga_art":False,
            "external_editor_integration":"read-only doctor; video handoff requires explicit source specification",
            "thumbnail":"Locally composed from real original panels, no AI image generation",
            "milestones":[
                {"id":"01","owner":"source","goal":"Import pages with hashes + RTL order","requires":[]},
                {"id":"02","owner":"story","goal":"Chapter-by-chapter event and panel script","requires":["01"]},
                {"id":"03","owner":"audio","goal":"Cast narrator and dialogue with reliable timing","requires":["02"]},
                {"id":"04","owner":"editing","goal":"Build 3–5 minute reviewable segments","requires":["03"]},
                {"id":"05","owner":"qa","goal":"Verify speech/story/panel synchronization","requires":["04"]},
                {"id":"06","owner":"editing","goal":"Assemble and decode longform 1080p video","requires":["05"]},
                {"id":"07","owner":"thumbnail","goal":"Original-panel thumbnail, title, chapter SEO","requires":["06"]},
                {"id":"08","owner":"publishing","goal":"Human approval then private upload","requires":["07"]},
            ],
            "release_approved":False,
            "created_at":now(),
        }
        target.write_text(json.dumps(plan,indent=2,ensure_ascii=False)+"\n",encoding="utf8")
        add_message("management",f"Created an eight-stage dependency-tracked plan. "
                    "No stage is marked complete without evidence. "
                    "Director/Operator are GPT-6 roles; other departments are verifiable workers.",
                    evidence=str(target))
        return {"ok":True,"reused":False,"path":str(target),"milestones":8}
    if action=="review-gates":
        h=refresh_status()
        conditions={"panels_imported":h["sources_ready"],"script_verified":False,
                    "all_dialogue_matched":False,"final_mp4_reviewed":False,
                    "source_art_thumbnail_reviewed":False,"public_release_approved":False}
        result={"ok":False,"checks":conditions,"release_allowed":False}
        add_message("qa","Release gate: NOT APPROVED. Missing verified panel-script alignment, "
                    "complete finished render, human audiovisual review and final thumbnail. "
                    "This is a factual gate, not an error.",evidence=str(PROJECT))
        add_message("publishing","No release action will run until video QC and user approval are recorded. "
                    "No upload has been made.")
        return result
    raise ValueError("Unknown action")

def launch(action):
    if action not in ACTIONS:raise ValueError("Unknown work action")
    with LOCK:
        if action in ACTIVE:return False
        ACTIVE.add(action)
    def run():
        with db_open() as db:
            cur=db.execute("INSERT INTO jobs(action,status,started) VALUES(?,?,?)",(action,"running",now()))
            jid=cur.lastrowid
            db.commit()
        try:
            result=execute(action)
            status="done" if result.get("ok") else "blocked"
        except Exception as exc:
            result={"ok":False,"error":f"{type(exc).__name__}: {str(exc)[:260]}"}
            status="failed"
            add_message("management",f"Action {action} failed: {result['error']}. No success recorded.")
        with db_open() as db:
            db.execute("UPDATE jobs SET status=?,ended=?,result=? WHERE id=?",
                       (status,now(),json.dumps(result,ensure_ascii=False)[:16000],jid))
            db.commit()
        with LOCK:ACTIVE.discard(action)
    threading.Thread(target=run,name=f"studio-{action}",daemon=True).start()
    return True

def snapshot():
    with db_open() as db:
        msgs=[dict(x) for x in db.execute(
            "SELECT id,channel,role,origin,body,ts,evidence FROM messages ORDER BY id DESC LIMIT 250").fetchall()][::-1]
        tasks=[dict(x) for x in db.execute("SELECT * FROM tasks ORDER BY rowid")]
        jobs=[dict(x) for x in db.execute("SELECT id,action,status,started,ended FROM jobs ORDER BY id DESC LIMIT 25")]
        inbox=db.execute("SELECT COUNT(*) FROM inbox WHERE status='pending'").fetchone()[0]
    try:
        import sys
        if str(REPO) not in sys.path:
            sys.path.insert(0, str(REPO))
        from ashentoons.gemini_tts import credential_ready
        google_configured = credential_ready()
    except (OSError,ImportError,ValueError):
        google_configured = False
    heartbeat=LOGS/"crew-heartbeat.json"
    try:
        crew=json.loads(heartbeat.read_text(encoding="utf8")) if heartbeat.is_file() else {}
        crew_online=(time.time()-float(crew.get("timestamp",0))) < 38
        crew_status=crew.get("status","offline") if crew_online else "offline"
    except (OSError,ValueError,TypeError):
        crew_online,crew_status=False,"offline"
    return {"departments":DEPARTMENTS,"messages":msgs,"tasks":tasks,"jobs":jobs,
            "pending_gpt6":inbox,"active":sorted(ACTIVE),
            "local_crew_online":crew_online,"local_crew_status":crew_status,
            "local_crew_model":"Qwen3.5:9B" if crew_online else None,
            "google_tts_configured":google_configured,
            "model":"GPT-6 • connected session","runtime":"Deterministic local workers",
            "project":"The Wrong Way to Use Healing Magic","project_id":"healing-magic-001"}

def received_user(body,target="group"):
    body=str(body).strip()
    if not 1<=len(body)<=2200 or target not in BY_ID and target!="group":
        raise ValueError("Invalid message")
    add_message("you",body,origin="user",channel=target)
    with LOCK,db_open() as db:
        db.execute("INSERT INTO inbox(channel,body,status,ts) VALUES(?,?,'pending',?)",
                   (target,body,now()))
        db.commit()
    if target in ("ceo","operator"):
        add_message("management",
                    "Queued for GPT-6 in the connected ChatGPT conversation. This is not an unattended GPT-6 API.",
                    origin="system",channel=target)
    lowered=body.casefold()
    # Strict, harmless known action mappings for useful department replies.
    permitted=None
    if target in ("audio",) and any(k in lowered for k in ("check","audit","verify","status","voice")):
        permitted="audit-cast"
    elif target in ("source",) and any(k in lowered for k in ("check","audit","scan","status","chapters")):
        permitted="scan-sources"
    elif target in ("qa",) and any(k in lowered for k in ("check","audit","verify","release","status")):
        permitted="review-gates"
    elif target in ("editing",) and any(k in lowered for k in ("check","doctor","status")):
        permitted="audit-editor"
    elif target in ("management",) and any(k in lowered for k in ("plan","schedule","stages")):
        permitted="create-plan"
    if permitted:launch(permitted)

class Handler(BaseHTTPRequestHandler):
    server_version="AshenToonsHQ/1.0"
    def log_message(self,*args):pass
    def _authorized(self):
        ip=ipaddress.ip_address(self.client_address[0])
        if not (ip.is_loopback or ip in ipaddress.ip_network("192.168.1.0/24")):
            return False
        from urllib.parse import parse_qs
        key=parse_qs(urlsplit(self.path).query).get("key",[""])[0]
        header=self.headers.get("X-Ashen-Token","")
        return secrets.compare_digest(key,SECRET.read_text("utf8").strip()) or secrets.compare_digest(header,SECRET.read_text("utf8").strip())
    def _respond(self,data,status=200,typ="application/json; charset=utf-8"):
        blob=data if isinstance(data,bytes) else json.dumps(data,ensure_ascii=False).encode("utf8")
        self.send_response(status)
        self.send_header("Content-Type",typ)
        self.send_header("Content-Length",str(len(blob)))
        self.send_header("Cache-Control","no-store")
        self.send_header("X-Content-Type-Options","nosniff")
        self.send_header("X-Frame-Options","DENY")
        self.send_header("Referrer-Policy","no-referrer")
        self.send_header("Content-Security-Policy","default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; media-src 'self'; connect-src 'self'; object-src 'none'; frame-ancestors 'none'")
        self.end_headers()
        self.wfile.write(blob)
    def do_GET(self):
        path=urlsplit(self.path).path
        if path=="/open":
            # One-click access only from the same physical computer.
            # Remote LAN clients must use the existing private token.
            local=ipaddress.ip_address(self.client_address[0]).is_loopback
            host=self.headers.get("Host","").casefold()
            if not local or host not in {f"127.0.0.1:{PORT}",f"localhost:{PORT}"}:
                return self._respond({"error":"Open this from the laptop itself"},403)
            self.send_response(303)
            self.send_header("Location","/?key="+SECRET.read_text("utf8").strip())
            self.send_header("Cache-Control","no-store")
            self.send_header("Referrer-Policy","no-referrer")
            self.send_header("Content-Length","0")
            self.end_headers()
            return
        if not self._authorized():
            return self._respond({"error":"Private studio: valid access token required"},403)
        static_paths={"/":"index.html","/app.js":"app.js","/styles.css":"styles.css"}
        if path in static_paths:
            name=static_paths[path]
            f=STATIC/name
            if not f.is_file():return self._respond({"error":"Static asset missing"},404)
            typ="text/html; charset=utf-8" if name.endswith("html") else "text/javascript; charset=utf-8" if name.endswith("js") else "text/css; charset=utf-8"
            payload=f.read_bytes()
            if name=="index.html":
                payload=payload.replace(b"{{KEY}}",SECRET.read_text(encoding="utf8").strip().encode("utf8"))
            return self._respond(payload,typ=typ)
        if path.startswith("/avatars/") and re.fullmatch(r"/avatars/[a-z]+\.svg",path):
            f=AVATARS/Path(path).name
            if f.is_file():return self._respond(f.read_bytes(),typ="image/svg+xml")
        if path=="/media/audition.mp3":
            f=PROJECT/"auditions"/"healing-magic-cast-audition.mp3"
            if f.is_file() and f.stat().st_size<=10_000_000:
                return self._respond(f.read_bytes(),typ="audio/mpeg")
        if path=="/api/state":return self._respond(snapshot())
        if path=="/api/health":return self._respond({"ok":True,"project":str(PROJECT),"server":"AshenToons HQ"})
        return self._respond({"error":"Not found"},404)
    def do_POST(self):
        if not self._authorized():return self._respond({"error":"Forbidden"},403)
        from urllib.parse import urlsplit
        origin=self.headers.get("Origin")
        if origin:
            allowed={f"http://localhost:{PORT}",f"http://127.0.0.1:{PORT}",f"http://192.168.1.66:{PORT}"}
            if origin not in allowed:return self._respond({"error":"Cross-origin requests denied"},403)
        try:
            length=int(self.headers.get("Content-Length","0"))
            if not 1<=length<=10000:raise ValueError("Payload too large")
            data=json.loads(self.rfile.read(length).decode("utf8"))
            if not isinstance(data,dict):raise ValueError("Object expected")
            endpoint=urlsplit(self.path).path
            if endpoint=="/api/send":
                received_user(data.get("body",""),data.get("target","group"))
                return self._respond({"ok":True,"note":"Queued for GPT-6 and logged in group"})
            if endpoint=="/api/run":
                action=data.get("action")
                if action not in ACTIONS:raise ValueError("Unknown approved action")
                success=launch(action)
                return self._respond({"ok":success,"action":action},202 if success else 409)
            return self._respond({"error":"Unknown endpoint"},404)
        except (ValueError,UnicodeError,TypeError) as exc:
            return self._respond({"error":str(exc)[:200]},400)

def main():
    initialize()
    refresh_status()
    parser=argparse.ArgumentParser()
    parser.add_argument("--serve",action="store_true")
    parser.add_argument("--smoke",action="store_true")
    parser.add_argument("--action",choices=sorted(ACTIONS))
    args=parser.parse_args()
    if args.smoke:
        print(json.dumps({"ok":True,"roles":len(DEPARTMENTS),"tests":len(ACTIONS),"tasks":len(TASK_ROWS),"data":str(DB),"project":inspector()},indent=2,ensure_ascii=False))
        return
    if args.action:
        print(json.dumps(execute(args.action),ensure_ascii=False,indent=2))
        return
    if args.serve:
        key=SECRET.read_text("utf8").strip()
        print("ASHENTOONS_HQ_URL=http://192.168.1.66:8770/?key="+key,flush=True)
        print("SERVER_AUTH_REQUIRED=true MODE=GPT-6-connected-plus-local-workers",flush=True)
        ThreadingHTTPServer((BIND,PORT),Handler).serve_forever()
        return
    parser.print_help()

if __name__=="__main__":main()
