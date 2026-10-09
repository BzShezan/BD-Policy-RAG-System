import argparse
import asyncio
import json
import logging
import sys
from .config import Settings
from .orchestrator import Orchestrator
from .base_orchestrator import BaseOrchestrator
from .schemas import Query

def main():
    parser=argparse.ArgumentParser(description="Unmochon Live Week 1")
    sub=parser.add_subparsers(dest="command",required=True)
    ask=sub.add_parser("ask");ask.add_argument("question");ask.add_argument("--json",action="store_true")
    update=sub.add_parser("update-dataset", help="Offline original-filtered ChromaDB + BM25 update")
    update.add_argument("folder")
    update.add_argument("--metadata", help="Original-format doc_metadata.json updates")
    sub.add_parser("chat")
    sub.add_parser("doctor")
    serve=sub.add_parser("serve");serve.add_argument("--host",default="127.0.0.1");serve.add_argument("--port",type=int,default=8000)
    args=parser.parse_args();settings=Settings.load()
    if args.command=="update-dataset":
        from .datasets import update_dataset
        print(json.dumps(update_dataset(args.folder, args.metadata), ensure_ascii=False, indent=2));return
    if args.command=="serve":
        if args.host not in {"127.0.0.1","localhost","::1"} and not settings.api_key:
            parser.error("A non-loopback bind requires API_KEY; set APP_ENV=production for deployment")
        import uvicorn
        from .api import create_app
        print(f"Unmochon search UI: http://{args.host}:{args.port}")
        uvicorn.run(create_app(settings),host=args.host,port=args.port);return
    if args.command=="doctor":
        from .doctor import diagnose
        print(json.dumps(diagnose(settings), ensure_ascii=False, indent=2));return
    logging.basicConfig(level=logging.WARNING)
    if settings.rag_backend == "original":
        from filelock import FileLock
        database_lock = FileLock(str(settings.root / ".database.lock"), timeout=0)
        database_lock.acquire()  # released automatically on process exit

    engine=(BaseOrchestrator(settings) if settings.rag_backend == "original" else Orchestrator(settings))
    async def run():
        if args.command=="ask":
            result=await engine.ask(Query(question=args.question))
            print(result.model_dump_json(indent=2) if args.json else f"Route: {result.route} | Status: {result.status}\n\n{result.answer}\n\n"+"\n".join(result.warnings));return
        print("Unmochon Live — type exit to quit; live sources may be unavailable.")
        while True:
            try:q=await asyncio.to_thread(input,"আপনি > ")
            except (EOFError,KeyboardInterrupt):break
            if q.lower().strip() in {"exit","quit"}:break
            if len(q.strip())<2:continue
            result=await engine.ask(Query(question=q))
            print(f"[{result.route} / {result.status}]\n{result.answer}\n")
    try:
        asyncio.run(run())
    except KeyboardInterrupt:
        print("\nবিদায়।")
