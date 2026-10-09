"""Run in the teammate's CURRENT RAG environment after implementing their adapter.
This is an integration template, NOT the missing original retriever.
Set TEAMMATE_PROJECT_ROOT and TEAMMATE_SEARCH_CALLABLE=module:function.
The function must return docs/TEAMMATE_CONTRACT.md shape and load models once.
Start: python -m uvicorn scripts.teammate_api_example:app --port 8101
Install FastAPI/Uvicorn here only if absent; agent dependencies remain isolated.
"""
import asyncio
import importlib
import os
import secrets
import sys
from contextlib import asynccontextmanager
from fastapi import FastAPI,Header,HTTPException
from pydantic import BaseModel,Field

class SearchRequest(BaseModel):
    schema_version:str="1.0"
    question:str=Field(min_length=2,max_length=2000)
    top_k:int=Field(default=3,ge=1,le=10)

@asynccontextmanager
async def lifespan(app):
    root=os.environ.get("TEAMMATE_PROJECT_ROOT")
    if root:sys.path.insert(0,root)
    target=os.environ.get("TEAMMATE_SEARCH_CALLABLE")
    if not target:raise RuntimeError("Set TEAMMATE_SEARCH_CALLABLE to your real adapter module:function")
    module,name=target.split(":",1)
    app.state.search=getattr(importlib.import_module(module),name)
    app.state.lock=asyncio.Lock()
    yield
app=FastAPI(lifespan=lifespan)

@app.post("/v1/search")
async def search(body:SearchRequest,x_api_key:str|None=Header(default=None)):
    key=os.environ.get("RAG_API_KEY","")
    if not key or not secrets.compare_digest(x_api_key or "",key):
        raise HTTPException(401,"RAG_API_KEY required")
    if body.schema_version!="1.0":raise HTTPException(422,"Unsupported contract version")
    # Serialise a local Chroma/model backend unless its owner confirms thread safety.
    async with app.state.lock:
        return await asyncio.to_thread(app.state.search,body.question,body.top_k)
