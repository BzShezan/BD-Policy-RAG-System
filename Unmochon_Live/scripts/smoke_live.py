"""Opt-in real network probe. Unavailability is a recorded outcome, not a passed live answer."""
import asyncio
import json
from unmochon_live.config import Settings
from unmochon_live.orchestrator import Orchestrator
from unmochon_live.schemas import Query
async def main():
    engine=Orchestrator(Settings.load())
    for question in ["বয়স্ক ভাতার বয়স কত?","নতুন NID করার জন্য কী কী কাগজপত্র লাগবে?","e-passport করতে কী কী documents প্রয়োজন?"]:
        r=await engine.ask(Query(question=question))
        print(json.dumps({"question":question,"route":r.route,"status":r.status,"backend":r.backend,
            "elapsed_ms":r.elapsed_ms,"source_count":len(r.evidence),"trace":r.trace},ensure_ascii=False))
asyncio.run(main())
