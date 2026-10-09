"""Batch narration for authored AshenToons script lines.

No story text generated here. A batch synthesizes only the explicit existing
script lines, with fixed per-character voice assignments, per-line SHA cache
and timestamped WAV manifest for subsequent scene-by-scene editorial review.
Production can resume after a rate-limit failure without erasing old audio.
"""
from __future__ import annotations
from hashlib import sha256
import json
import os
from pathlib import Path
import tempfile

from .gemini_tts import (
    GOOGLE_MODEL, DEFAULT_GOOGLE_CAST, DEFAULT_KOKORO_CAST,
    credential_ready, synthesize_google, line_cache_path, probe_wave,
)
from .core import file_hash


def batch_narrate_google(script: dict, audio_folder: Path,
                         output_manifest: Path, *, model: str = GOOGLE_MODEL,
                         max_new_requests: int = 12, approve_api_charges: bool = False,
                         fallback_to_kokoro: bool = False,
                         synth=None, local_synth=None) -> dict:
    """Export synchronized 24kHz WAV files; return FAIL when any line is missing.

    All segment text must be grounded and prepared by the story department.
    max_new_requests caps *possible* billable calls within one batch.
    """
    if (not isinstance(script, dict) or not isinstance(script.get("clips"), list)
            or not 1 <= len(script["clips"]) <= 150
            or not isinstance(audio_folder, Path) or not isinstance(output_manifest, Path)
            or output_manifest.suffix.lower() != ".json"
            or output_manifest.exists() or output_manifest.is_symlink()
            or audio_folder.is_symlink()
            or type(max_new_requests) is not int or not 1 <= max_new_requests <= 48):
        return {"status":"FAIL","errors":["Invalid batch script or existing output"]}
    clips=script["clips"]
    google_voices=script.get("google_voices", DEFAULT_GOOGLE_CAST)
    kokoro_voices=script.get("voices", DEFAULT_KOKORO_CAST)
    if (not isinstance(google_voices,dict) or not isinstance(kokoro_voices,dict)
            or any(not isinstance(x,dict) for x in clips)):
        return {"status":"FAIL","errors":["Invalid cast or line objects"]}
    from .gemini_tts import GOOGLE_VOICES, SUPPORTED_GOOGLE_MODELS
    from .tts import SUPPORTED_VOICES
    if model not in SUPPORTED_GOOGLE_MODELS:
        return {"status":"FAIL","errors":["Unsupported Gemini TTS model"]}
    prepared=[]
    for i,clip in enumerate(clips):
        speaker=clip.get("speaker","MC")
        line=clip.get("narration",clip.get("text"))
        if (not isinstance(speaker,str) or speaker not in google_voices or
                google_voices[speaker] not in GOOGLE_VOICES or
                speaker not in kokoro_voices or kokoro_voices[speaker] not in SUPPORTED_VOICES
                or not isinstance(line,str) or not 1<=len(line.strip())<=400
                or not isinstance(clip.get("event_id"),str) or not clip["event_id"]
                or len(clip["event_id"])>120):
            return {"status":"FAIL","errors":[f"line[{i}] requires an event ID, valid speaker and <=400 characters"]}
        voice=google_voices[speaker]
        style=clip.get("voice_style","natural cinematic storytelling")
        if not isinstance(style,str) or len(style)>180:
            return {"status":"FAIL","errors":[f"line[{i}] invalid delivery direction"]}
        path=line_cache_path(audio_folder,line,voice,style,model)
        prepared.append((speaker,line,clip["event_id"],voice,style,path,clip))
    if not approve_api_charges:
        return {"status":"BLOCKED","errors":["Explicit Google API charge approval required for a batch"]}
    ready=credential_ready()
    if not ready and not fallback_to_kokoro:
        return {"status":"BLOCKED","errors":["Google API key not yet configured"]}
    google_function=synth or synthesize_google
    completed=[]
    new_requests=0
    reused=0
    fallback_count=0
    audio_folder.mkdir(parents=True,exist_ok=True)
    for i,(speaker,line,event_id,voice,style,path,clip) in enumerate(prepared):
        cached=probe_wave(path) if path.is_file() else {"status":"FAIL"}
        result=None
        if cached.get("status")=="PASS":
            result={"status":"PASS","path":str(path),"voice":voice,
                    "duration":cached["duration"],"sha256":cached["sha256"],
                    "engine":"google","reused":True}
            reused+=1
        elif path.exists() or path.is_symlink():
            return {"status":"FAIL","errors":[f"line[{i}] cached WAV corrupt; preserve for investigation"],"completed":i}
        elif ready:
            if new_requests>=max_new_requests:
                return {"status":"PARTIAL","errors":[f"Reached {max_new_requests} Google API requests in this run; rerun to reuse cached audio"],
                        "completed":i,"new_requests":new_requests,"reused":reused}
            new_requests+=1
            result=google_function(line,path,voice=voice,model=model,style=style)
            result={"engine":"google",**result}
        else:
            result={"status":"BLOCKED","errors":["Google key not set"],"engine":"google"}
        if result["status"]!="PASS" and fallback_to_kokoro:
            from .tts import synthesize as kokoro_synthesize
            local=local_synth or kokoro_synthesize
            v=kokoro_voices[speaker]
            key=sha256(("kokoro-rescue-v1|"+v+"|"+line.strip()).encode("utf8")).hexdigest()[:32]
            rescue=audio_folder/("kokoro-"+key+".wav")
            exists=probe_wave(rescue) if rescue.is_file() else {"status":"FAIL"}
            if exists.get("status")=="PASS":
                result={"status":"PASS","path":str(rescue),"voice":v,"duration":exists["duration"],
                        "sha256":exists["sha256"],"engine":"kokoro","reused":True}
            elif rescue.exists() or rescue.is_symlink():
                return {"status":"FAIL","errors":[f"line[{i}] cached fallback WAV corrupt"],"completed":i}
            else:
                original=local(line,rescue,voice=v)
                result={"engine":"kokoro",**original}
            if result["status"]=="PASS":fallback_count+=1
        if result["status"]!="PASS":
            return {"status":"PARTIAL","errors":[f"line[{i}] {result.get('engine','Google')} synthesis unavailable; audio already made is reusable"],
                    "detail":result.get("errors",[]),"completed":i,
                    "new_requests":new_requests,"reused":reused}
        checked=probe_wave(Path(result["path"]))
        if checked["status"]!="PASS":
            return {"status":"FAIL","errors":[f"line[{i}] generated audio did not pass WAV integrity"],"completed":i}
        try:
            audio_relative=Path(result["path"]).resolve(strict=True).relative_to(audio_folder.resolve(strict=True)).as_posix()
        except (OSError,ValueError):
            return {"status":"FAIL","errors":[f"line[{i}] unsafe audio output path"],"completed":i}
        completed.append({
            "speaker":speaker,"event_id":event_id,
            "chapter":clip.get("chapter"),"text":line,
            "engine":result.get("engine","google"),"voice":result["voice"],
            "voice_style":style,"audio":audio_relative,
            "audio_sha256":checked["sha256"],
            "duration":checked["duration"],
            "requires_story_scene_review":True,
        })
    summary={
        "version":1,"type":"ashentoons voice-only production",
        "script_name":script.get("series","AshenToons"),
        "audio_root":str(audio_folder),
        "model":model,"roles":google_voices,
        "status":"READY_FOR_STORY_SCENE_REVIEW",
        "new_api_requests":new_requests,"cache_reused":reused,
        "kokoro_fallbacks":fallback_count,
        "complete":len(completed)==len(clips),
        "no_subtitles":True,"no_generated_panels":True,
        "release_approved":False,
        "clips":completed,
    }
    output_manifest.parent.mkdir(parents=True,exist_ok=True)
    fd,tmp=tempfile.mkstemp(prefix=".voices-",suffix=".json",dir=output_manifest.parent)
    try:
        with os.fdopen(fd,"w",encoding="utf8") as stream:
            json.dump(summary,stream,ensure_ascii=False,indent=2)
            stream.write("\n")
        if output_manifest.exists() or output_manifest.is_symlink():
            return {"status":"FAIL","errors":["Manifest destination appeared during generation"]}
        os.replace(tmp,output_manifest)
        return {"status":"PASS","manifest":str(output_manifest),
                "clips":len(completed),"new_api_requests":new_requests,
                "reused":reused,"kokoro_fallbacks":fallback_count,
                "ready_to_publish":False}
    finally:
        Path(tmp).unlink(missing_ok=True)
