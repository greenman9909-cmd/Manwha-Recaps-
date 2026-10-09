"""AshenToons Crew — local conversational production assistants.

This is a local Ollama/Qwen crew, *not* ten independent GPT-6 sessions.
GPT-6 makes high-stakes creative decisions in connected ChatGPT and
uses bridge.py to access the same real group chat.

Safety:
- No arbitrary shell execution from chat.
- Only small predefined read-only work actions.
- Narration, source downloading, generation, and uploading are NOT launched.
- No API keys, browser tokens, private credentials or user files enter prompts.
- No false completion: evidence is produced only by deterministic tools.
- Retries and timeouts are bounded; worker status is recorded in SQLite.
"""
from __future__ import annotations
import json
import os
from pathlib import Path
import re
import sqlite3
import sys
import threading
import time
import urllib.error
import urllib.request
import uuid

import server as studio

MODEL = "qwen3.5:9b"
ENDPOINT = "http://127.0.0.1:11434/api/chat"
HEARTBEAT = studio.LOGS / "crew-heartbeat.json"
POLL_SECONDS = 1.6
ROLES = {d["id"]: d for d in studio.DEPARTMENTS if d["id"] not in ("ceo", "operator")}
OPENAI_ROLES = {"ceo", "operator"}
GUIDANCE = {
    "management": ["plan", "manage", "project", "priority", "status", "team", "schedule", "finish", "ready", "progress", "deadline", "start"],
    "source": ["panel", "manga", "chapter", "source", "me manga", "memanga", "import", "download", "pages", "rights"],
    "story": ["story", "script", "scene", "dialogue", "plot", "character", "arc", "continuity", "recap", "pacing"],
    "audio": ["voice", "narrat", "kokoro", "fenrir", "google", "gemini tts", "sound", "audio", "dub", "character voice"],
    "editing": ["edit", "clip", "render", "video", "animation", "motion", "effect", "transition", "ffmpeg", "export", "flow mcp"],
    "qa": ["test", "quality", "qa", "verify", "accuracy", "match", "check", "audit", "review", "sync"],
    "thumbnail": ["thumbnail", "title", "seo", "metadata", "hook", "views", "cover", "click", "poster"],
    "publishing": ["publish", "upload", "youtube", "private", "release", "visibility"],
}
CHECK_ACTION = {
    "management":"readiness",
    "source":"scan-sources",
    "story":"readiness",
    "audio":"audit-cast",
    "editing":"audit-editor",
    "qa":"review-gates",
    "thumbnail":"review-gates",
    "publishing":"review-gates",
}

def migrate():
    studio.initialize()
    with studio.db_open() as db:
        cols={row["name"] for row in db.execute("PRAGMA table_info(inbox)")}
        if "local_status" not in cols:
            db.execute("ALTER TABLE inbox ADD COLUMN local_status TEXT NOT NULL DEFAULT 'new'")
        if "local_reply" not in cols:
            db.execute("ALTER TABLE inbox ADD COLUMN local_reply INTEGER")
        # A previous interrupted run may leave a claim. Re-queue on clean start.
        db.execute("UPDATE inbox SET local_status='new' WHERE local_status='processing'")
        db.commit()

def heartbeat(stage="idle", description="Ready"):
    studio.LOGS.mkdir(exist_ok=True)
    data={"pid":os.getpid(), "model":MODEL, "status":stage, "description":description,
          "timestamp":time.time(), "kind":"local_ai_not_gpt6"}
    temp=HEARTBEAT.with_suffix(".tmp")
    temp.write_text(json.dumps(data), encoding="utf8")
    os.replace(temp, HEARTBEAT)

def next_request():
    with studio.LOCK,studio.db_open() as db:
        row=db.execute(
            "SELECT id,channel,body,ts FROM inbox WHERE local_status='new' ORDER BY id LIMIT 1"
        ).fetchone()
        if not row:return None
        cur=db.execute("UPDATE inbox SET local_status='processing' "
                       "WHERE id=? AND local_status='new'",(row["id"],))
        db.commit()
        return dict(row) if cur.rowcount else None

def complete_request(request, status="replied", message_id=None):
    with studio.LOCK,studio.db_open() as db:
        db.execute("UPDATE inbox SET local_status=?,local_reply=? WHERE id=?",
                   (status, message_id, request["id"]))
        db.commit()

def route(message, target):
    if target in ROLES:return target
    if target in OPENAI_ROLES:return target
    lower=message.casefold()
    tagged=re.search(r"@([a-zA-Z]+)",lower)
    if tagged:
        for role, cfg in ROLES.items():
            if tagged.group(1) in (role,cfg["name"].casefold()):
                return role
    if any(term in lower for term in ("thumbnail","seo","cover art","video title")):
        return "thumbnail"
    scores={role:sum(len(word)>0 and word in lower for word in words) for role,words in GUIDANCE.items()}
    top=max(scores,key=lambda r:(scores[r],r=="management"))
    return top if scores[top] else "management"

def check_intent(message):
    lower=message.casefold()
    return bool(re.search(r"\b(status|audit|scan|check|inspect|test|verify|diagnose|doctor)\b",lower))

def read_only_action(role, body):
    """Only predefined, non-destructive checker functions may run automatically."""
    action=CHECK_ACTION.get(role)
    if not check_intent(body) or not action:
        return None
    try:
        # Use the already reviewed deterministic implementation, with
        # auditable job records and independent department messages.
        accepted=studio.launch(action)
        return action if accepted else None
    except Exception:
        return None

def redact(text):
    # Keep API credentials and access-token patterns out of any local model logs.
    value=str(text)[:1600]
    value=re.sub(r"(AIza[A-Za-z0-9_.-]{15,}|AQ\.[A-Za-z0-9_.-]{20,})","[REDACTED KEY]",value)
    value=re.sub(r"(?i)(key|token|password|secret)\s*[=:]\s*\S+",r"\1=[REDACTED]",value)
    return value

def evidence_summary():
    h=studio.inspector()
    t=[]
    try:
        with studio.db_open() as db:
            t=[dict(row) for row in db.execute("SELECT id,status,note FROM tasks ORDER BY rowid")]
    except sqlite3.Error:
        pass
    return {
        "project":h["project"],
        "mc_voice":h["mc_voice"],
        "cast_tested":h["cast_ready"],
        "original_chapters_imported":len(h["chapters"]),
        "provenance_verified":h["sources_ready"],
        "panel_script_available":h["script_ready"],
        "finished_manga_video":bool(h["videos"]),
        "script_candidates":len(h["story_scripts"]),
        "standalone_editor_installed":h["standalone_editor_installed"],
        "voice_api_configured":studio.snapshot().get("google_tts_configured",False),
        "tasks":t,
    }

def persona_system(role, evidence):
    cfg=ROLES[role]
    return (
        f"You are {cfg['name']}, AshenToons {cfg['title']}, a LOCAL Qwen studio persona. "
        f"Personality: {cfg['tone']} Motto: {cfg['motto']} "
        "You are NOT GPT-6 and must NEVER impersonate GPT-6, suggest you have independently "
        "executed tools, or claim a video/page/render/upload exists without the factual evidence below. "
        "You can reason, brainstorm, identify blockers, and suggest concrete next tasks, "
        "but work is complete ONLY when local tool checks create evidence. "
        "Never mention or ask for an API key in chat. Never claim a Google request was made. "
        "Never suggest bypassing access controls. Use actual authorized artwork rather than AI-generated manga panels. "
        "The human wants engaging original English recaps, accurate synced panels, NO added subtitles, "
        "distinct Kokoro voices with MC am_fenrir, and local HQ communication. "
        "Be candid, competent, casual but not childish, and concise (2–4 sentences). "
        "If blocked, say precisely what is missing and next safe action. "
        "Do not output Markdown headings, JSON, or fake progress metrics. "
        "CURRENT FACTS: "+json.dumps(evidence,ensure_ascii=False,separators=(",",":"))[:2600]
    )

def generate(role, body, evidence=None, timeout=75):
    evidence=evidence if evidence is not None else evidence_summary()
    request_payload={
        "model":MODEL,
        "messages":[
            {"role":"system","content":persona_system(role,evidence)},
            {"role":"user","content":redact(body)},
        ],
        "stream":False,
        "think":False,
        "keep_alive":"30s",
        "options":{"temperature":0.32,"num_predict":180,"num_ctx":3072,"repeat_penalty":1.07},
    }
    req=urllib.request.Request(
        ENDPOINT,data=json.dumps(request_payload).encode("utf8"),
        headers={"Content-Type":"application/json"},method="POST")
    with urllib.request.urlopen(req,timeout=timeout) as response:
        result=json.load(response)
    answer=result.get("message",{}).get("content","")
    answer=re.sub(r"(?s)<think>.*?</think>","",str(answer))
    answer=answer.strip()
    if not answer:raise ValueError("Local model returned an empty answer")
    return redact(answer)[:1150]

def safe_fallback(role, evidence):
    if not evidence["provenance_verified"]:
        return ("I checked the current production prerequisites. Healing Magic manga pages "
                "aren't imported, so our story team cannot verify the narration or begin the hour-long render. "
                "The cast auditions and editing tools are usable; importing the correct chapters comes first.")
    if not evidence["panel_script_available"]:
        return ("Chapter pages are available, but there is no verified panel-to-script mapping yet. "
                "Story needs to connect each line to a real page before editing can begin.")
    return ("The source/script prerequisites exist, but QC has not approved a finished episode. "
            "I'll keep the release blocked until scene alignment and final A/V review are evidenced.")

def handle_request(request):
    channel=request["channel"];body=request["body"]
    target=route(body,channel)
    if target in OPENAI_ROLES:
        # Bridge.py deliberately leaves these in GPT-6's pending inbox.
        return None,"awaiting_gpt6"
    hb=f"Responding as {ROLES[target]['name']} to inbox #{request['id']}"
    heartbeat("generating",hb)
    if channel=="group" and re.search(
        r"\b(all.?team|everyone|whole team|all departments|team report|readiness)\b",body.casefold()
    ):
        studio.launch("readiness")
    check=read_only_action(target,body)
    grounded=evidence_summary()
    try:
        answer=generate(target,body,evidence=grounded)
    except (urllib.error.URLError,urllib.error.HTTPError,TimeoutError,OSError,
            ValueError,json.JSONDecodeError) as exc:
        answer=safe_fallback(target,grounded)
        print("LOCAL_MODEL_UNAVAILABLE",type(exc).__name__,flush=True)
    if check:
        answer += f"\n\nA separate verified {check} check was queued; its results will appear in Activity."
    # This provenance label prevents it from looking like a real GPT-6 reply.
    mid=studio.add_message(target,answer,origin="local_ai",channel=channel)
    return mid,"replied"

def work_once():
    entry=next_request()
    if entry is None:return False
    try:
        message_id,status=handle_request(entry)
        complete_request(entry,status=status,message_id=message_id)
    except Exception as error:
        studio.add_message("management",
            f"An automated response failed ({type(error).__name__}). The message stays in the GPT-6 review inbox.",
            origin="system",channel=entry["channel"])
        complete_request(entry,status="failed")
        print("CREW_ERROR",type(error).__name__,flush=True)
    return True

def run():
    migrate()
    print("ASHENTOONS_LOCAL_CREW_READY model="+MODEL,flush=True)
    last_hb=0
    while True:
        if time.time()-last_hb > 12:
            heartbeat()
            last_hb=time.time()
        if work_once():
            heartbeat()
            last_hb=time.time()
        else:
            time.sleep(POLL_SECONDS)

if __name__=="__main__":
    try: run()
    except KeyboardInterrupt:
        heartbeat("stopped","Keyboard interrupt")
