"""GPT-6 ChatGPT connector for AshenToons Control Room.

This adapter lets GPT-6 use its authorized Remote Desktop Commander to
receive real group-chat messages and post truthful decisions/results.
It does not call the OpenAI API or impersonate an always-on GPT-6.
"""
from __future__ import annotations
import argparse
import json
import sqlite3
from pathlib import Path
import server as studio

def inbox(limit=20):
    studio.initialize()
    with studio.db_open() as db:
        rows=[dict(x) for x in db.execute(
            "SELECT id,channel,body,status,ts FROM inbox WHERE status='pending' ORDER BY id LIMIT ?",(min(limit,100),))]
    print(json.dumps({"pending":rows,"count":len(rows)},indent=2,ensure_ascii=False))

def post(role,text,channel,proof=None,origin="gpt6"):
    studio.initialize()
    if role not in ("ceo","operator"):
        raise ValueError("GPT-6 messages require the CEO or Operator role")
    if origin!="gpt6":
        raise ValueError("Unsupported origin")
    if proof is not None and not Path(proof).exists():
        raise ValueError("Cited evidence path does not exist; refusing unsupported evidence")
    msg=studio.add_message(role,text,origin=origin,channel=channel,evidence=proof)
    print(json.dumps({"ok":True,"message_id":msg,"role":role,"channel":channel,"proof":proof},ensure_ascii=False))

def ack(message_id):
    studio.initialize()
    with studio.db_open() as db:
        row=db.execute("SELECT id,status FROM inbox WHERE id=?",(message_id,)).fetchone()
        if row is None:raise ValueError("Unknown inbox request")
        if row["status"]!="pending":raise ValueError("Already acknowledged")
        db.execute("UPDATE inbox SET status='handled' WHERE id=?",(message_id,))
        db.commit()
    print(json.dumps({"ok":True,"handled_inbox_id":message_id}))

def report():
    studio.initialize()
    snap=studio.snapshot()
    summary={"pending_messages":snap["pending_gpt6"],
             "tasks":snap["tasks"],
             "latest_chat":snap["messages"][-18:],
             "latest_runs":snap["jobs"][:10]}
    print(json.dumps(summary,indent=2,ensure_ascii=False))

def main():
    parser=argparse.ArgumentParser(description="GPT-6 <-> AshenToons studio bridge")
    sub=parser.add_subparsers(dest="cmd",required=True)
    sub.add_parser("inbox")
    sub.add_parser("report")
    m=sub.add_parser("post")
    m.add_argument("--role",choices=("ceo","operator"),required=True)
    m.add_argument("--message",required=True)
    m.add_argument("--channel",default="group",choices=("group",)+tuple(studio.BY_ID))
    m.add_argument("--proof",default=None,help="Existing local file path of evidence, optional")
    a=sub.add_parser("ack")
    a.add_argument("--id",type=int,required=True)
    args=parser.parse_args()
    if args.cmd=="inbox":inbox()
    if args.cmd=="report":report()
    if args.cmd=="post":post(args.role,args.message,args.channel,args.proof)
    if args.cmd=="ack":ack(args.id)

if __name__=="__main__":main()
