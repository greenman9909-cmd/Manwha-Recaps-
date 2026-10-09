"""Story-to-panel evidence requirements and review preparation.

Evidence fields make every edit traceable, but cannot prove a panel depicts
the claimed event. Independent inspection remains mandatory.
"""
from __future__ import annotations

import json
from pathlib import Path

ROLES = frozenset({
    "hook", "setup", "conflict", "reveal", "reaction",
    "payoff", "transition", "cliffhanger"
})


def audit_storyboard(manifest: dict) -> dict:
    errors = []
    clips = manifest.get("clips") if isinstance(manifest, dict) else None
    if not isinstance(clips, list) or not clips:
        return {"status": "FAIL", "errors": ["storyboard clips required"]}
    if len(clips) > 10000:
        return {"status": "FAIL", "errors": ["storyboard too large"]}
    for i, clip in enumerate(clips):
        if not isinstance(clip, dict):
            errors.append(f"clip[{i}]: invalid storyboard entry")
            continue
        for key in ("panel_summary", "match_reason"):
            value = clip.get(key)
            if not isinstance(value, str) or len(value.strip()) < 8 or len(value) > 2000:
                errors.append(f"clip[{i}]: {key} must be 8–2000 characters")
        chapter = clip.get("chapter")
        if type(chapter) is not int or chapter < 1 or chapter > 100000:
            errors.append(f"clip[{i}]: positive integer chapter required")
        role = clip.get("narrative_role")
        if role not in ROLES if isinstance(role, str) else True:
            errors.append(f"clip[{i}]: invalid narrative_role")
    return {
        "status": "FAIL" if errors else "PASS",
        "errors": errors,
        "checked_clips": len(clips),
        "note": "Field presence is not proof of semantic alignment",
    }


def review_template(manifest: dict, planned: dict) -> dict:
    """A per-shot, per-part human review sheet; all answers start unapproved."""
    if not isinstance(planned, dict) or planned.get("status") != "PASS":
        return {"status": "FAIL", "errors": ["passing segment plan required"]}
    if audit_storyboard(manifest)["status"] != "PASS":
        return {"status": "FAIL", "errors": ["storyboard evidence required"]}
    parts = []
    for part in planned["parts"]:
        shots = []
        for index in part["clip_indices"]:
            clip = manifest["clips"][index]
            shots.append({
                "clip_index": index, "chapter": clip["chapter"],
                "event_id": clip["event_id"], "panel": clip["panel"],
                "narration": clip["narration"],
                "panel_summary": clip["panel_summary"],
                "match_reason": clip["match_reason"],
                "narrative_role": clip["narrative_role"],
                "start": clip["start"], "end": clip["end"],
                "image_matches_narration": None,
                "character_continuity_ok": None,
                "visual_framing_ok": None,
                "notes": "",
            })
        parts.append({
            "part": part["part"],
            "duration": part["duration"],
            "reviewer": None,
            "audio_clear": None,
            "no_burned_subtitles": None,
            "no_offensive_or_misleading_framing": None,
            "reviewed": False,
            "shots": shots,
        })
    return {
        "status": "PENDING_HUMAN_REVIEW",
        "approved_for_publication": False,
        "parts": parts,
        "instructions": "Review the actual MP4 and authorized source panels independently; never mark approved based solely on manifest text.",
    }


def check_review(template: dict, expected_parts: int | None = None) -> dict:
    """A complete checklist is still not a license or publication authorization."""
    errors = []
    if not isinstance(template, dict) or not isinstance(template.get("parts"), list):
        return {"status": "FAIL", "errors": ["invalid review sheet"], "approved_for_publication": False}
    parts = template["parts"]
    if not parts or (expected_parts is not None and len(parts) != expected_parts):
        errors.append("incomplete review parts")
    for j, part in enumerate(parts):
        if not isinstance(part, dict):
            errors.append(f"part[{j}]: invalid record")
            continue
        if part.get("reviewed") is not True or not isinstance(part.get("reviewer"), str) or not part["reviewer"].strip():
            errors.append(f"part[{j}]: reviewer approval missing")
        for flag in ("audio_clear", "no_burned_subtitles", "no_offensive_or_misleading_framing"):
            if part.get(flag) is not True:
                errors.append(f"part[{j}]: {flag} not confirmed")
        shots = part.get("shots")
        if not isinstance(shots, list) or not shots:
            errors.append(f"part[{j}]: shot review missing")
            continue
        for i, shot in enumerate(shots):
            if not isinstance(shot, dict):
                errors.append(f"part[{j}].shot[{i}]: invalid entry")
                continue
            for flag in ("image_matches_narration", "character_continuity_ok", "visual_framing_ok"):
                if shot.get(flag) is not True:
                    errors.append(f"part[{j}].shot[{i}]: {flag} not confirmed")
    return {
        "status": "FAIL" if errors else "PASS",
        "errors": errors,
        "approved_for_publication": False,
        "note": "Review completion never substitutes for independent rights/release authorization",
    }
