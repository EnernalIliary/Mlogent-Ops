"""Atomically append requests to the server Agent's bounded inbox."""
import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path

INBOX = Path(os.environ.get('MLOGENT_PUSH_INBOX', "/www/dk_project/dk_app/astrbot/astrbot_Iliary/data/plugin_data/astrbot_plugin_world_push_inbox/inbox.json"))


def remember(group, rows):
    try:
        data = json.loads(INBOX.read_text(encoding="utf-8"))
    except (FileNotFoundError, ValueError):
        data = {}
    group = str(group)
    saved = data.get("rows", []) if data.get("group") == group else []
    received = datetime.now(timezone.utc).isoformat()
    known = {row.get("reply_id") for row in saved if row.get("reply_id")}
    incoming = [
        {"player": str(row.get("player") or "?")[:80],
         "text": str(row.get("message") or "")[:1600],
         "tick": row.get("tick"), "received_at": received, "reply_id": row.get("reply_id")}
        for row in rows if isinstance(row, dict) and row.get("reply_id") not in known and str(row.get("message") or "").strip()
    ]
    if not incoming:
        return
    fd, temp = tempfile.mkstemp(prefix="inbox.", dir=INBOX.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as file:
            json.dump({"group": group, "rows": (saved + incoming)[-50:]}, file, ensure_ascii=False)
        os.replace(temp, INBOX)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)
