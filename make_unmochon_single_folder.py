"""Localize the working app's existing assets; never rebuild or delete a source.

Place this file inside the working Unmochon folder. Stop its server, activate
unmochon_stage1, then run: python make_unmochon_single_folder.py --apply
Without --apply, this only prints the plan. No model downloads are performed.
"""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
import uuid

PATH_KEYS = ('SOURCE_REGISTRY','STAGE4_PACKAGE','STAGE6_PACKAGE','STAGE6_WORKSPACE','STAGE6_MODEL_PATH',
    'STAGE6_MODEL_CACHE','STAGE2_EVIDENCE_DATA','RESEARCH_SOURCE_REGISTRY','RESEARCH_OUTPUT_ROOT',
    'ORIGINAL_DATA_DIR','CORPUS_DIR','RAW_PDF_DIR','DOC_METADATA_PATH','PROCESSED_DIR',
    'CHROMADB_DIR','BM25_INDEX_PATH','EMBED_MODEL','TRANSLATION_MODEL',
    'STAGE4_OCR_MODELS','STAGE4_TESSERACT','STAGE6_PYTHON','HF_HOME','HF_HUB_CACHE',
    'HUGGINGFACE_HUB_CACHE','TRANSFORMERS_CACHE','TORCH_HOME')
LAUNCHER = '''"""Start this Unmochon folder using its own code and saved paths."""
import os
from pathlib import Path
import subprocess
import sys
from dotenv import dotenv_values
ROOT=Path(__file__).resolve().parent
KEYS=__PATH_KEYS__
env=dict(os.environ,PYTHONUTF8='1',PYTHONIOENCODING='utf-8',UNMOCHON_HOME=str(ROOT))
for k,v in dotenv_values(ROOT/'.env').items():
    if k in KEYS and v is not None:env[k]=v
env['RAG_BACKEND']='stage6'
env['PYTHONPATH']=str(ROOT/'src')+os.pathsep+str(ROOT)
print('Unmochon: http://127.0.0.1:8000',flush=True)
try:
    raise SystemExit(subprocess.call([sys.executable,'-X','utf8','-m','unmochon_live','serve'],cwd=ROOT,env=env))
except KeyboardInterrupt:
    pass
'''.replace('__PATH_KEYS__',repr(PATH_KEYS))


def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda:stream.read(4*1024*1024),b''):h.update(block)
    return h.hexdigest()


def atomic_bytes(path, data):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    temp=path.with_name('.sf-'+uuid.uuid4().hex[:12]+'.tmp')
    try:
        with temp.open('xb') as stream:
            stream.write(data);stream.flush();os.fsync(stream.fileno())
        os.replace(temp,path)
    finally:temp.unlink(missing_ok=True)


def json_bytes(value):
    return (json.dumps(value,ensure_ascii=False,indent=2)+'\n').encode('utf-8')


def env_bytes(previous, updates):
    remaining=dict(updates);lines=[]
    for line in previous.decode('utf-8-sig').splitlines():
        key=line.split('=',1)[0].strip() if '=' in line and not line.lstrip().startswith('#') else None
        if key in updates:
            if key in remaining:lines.append(key+'='+json.dumps(remaining.pop(key),ensure_ascii=False))
        else:lines.append(line)
    lines += [k+'='+json.dumps(v,ensure_ascii=False) for k,v in remaining.items()]
    return ('\n'.join(lines)+'\n').encode('utf-8')


class Assets:
    def __init__(self,root):
        self.root=Path(root).resolve();self.copies=[];self.paths={}

    def add(self,key,source,destination,required=False):
        source=Path(source).expanduser().absolute()
        if not source.exists():
            if required:raise ValueError('Required existing asset missing: '+key+' = '+str(source))
            return
        resolved=source.resolve()
        if resolved.is_relative_to(self.root):
            # File symlinks in HF snapshots may still lead to an old folder.
            items=list(resolved.rglob('*')) if resolved.is_dir() else [resolved]
            if any((p.is_symlink() or getattr(p,'is_junction',lambda:False)()) and p.is_dir()
                   and not p.resolve().is_relative_to(self.root) for p in items):
                raise ValueError('Asset directory is linked outside Unmochon: '+str(source))
            files=[p for p in items if p.is_file()]
            if all(p.resolve().is_relative_to(self.root) for p in files):
                self.paths[key]=resolved;return
        for old,new in self.copies:
            if resolved==old or (old.is_dir() and resolved.is_relative_to(old)):
                self.paths[key]=new/(resolved.relative_to(old)) if old.is_dir() else new
                return
        dest=self.root/destination
        if not dest.resolve().is_relative_to(self.root):
            raise ValueError('Destination is linked outside Unmochon: '+str(dest))
        if dest.resolve()==resolved:
            dest=dest.with_name(dest.name+'_localized')
        if dest.is_relative_to(resolved) or resolved.is_relative_to(dest):
            raise ValueError('Overlapping source/destination: '+key)
        self.copies.append((resolved,dest));self.paths[key]=dest

    def files(self):
        pairs=[]
        for source,dest in self.copies:
            items=sorted(source.rglob('*')) if source.is_dir() else [source]
            for p in items:
                if p.name=='.update.lock':continue
                if (p.is_symlink() or getattr(p,'is_junction',lambda:False)()) and p.resolve().is_dir():
                    raise ValueError('Directory symlink requires inspection: '+str(p))
                if p.is_file():
                    target=dest/p.relative_to(source) if source.is_dir() else dest
                    if not target.resolve().is_relative_to(self.root):
                        raise ValueError('Destination is linked outside Unmochon: '+str(target))
                    if target.is_symlink():raise ValueError('Destination symlink: '+str(target))
                    if target.exists() and (not target.is_file() or sha(target)!=sha(p)):
                        raise ValueError('Different existing destination; nothing overwritten: '+str(target))
                    pairs.append((p,target))
        return pairs


def copy_verified(source,target):
    source,target=Path(source),Path(target)
    before=sha(source)
    if target.exists():
        if sha(target)!=before:raise ValueError('Destination changed during consolidation')
        return
    target.parent.mkdir(parents=True,exist_ok=True)
    temp=target.with_name('.sf-'+uuid.uuid4().hex[:12]+'.tmp')
    try:
        shutil.copy2(source,temp)
        if sha(temp)!=before or sha(source)!=before:
            raise ValueError('Asset changed while copying: '+str(source))
        os.replace(temp,target)
    finally:temp.unlink(missing_ok=True)


def discover(root):
    """Resolve the currently working configuration and the pinned local model."""
    root=Path(root).resolve()
    if not (root/'src/unmochon_live/agentic_worker.py').is_file():
        raise ValueError('Place this script in the updated Unmochon folder')
    os.environ['UNMOCHON_HOME']=str(root);os.chdir(root)
    sys.path[:0]=[str(root/'src'),str(root)]
    if (root/'data/single_folder_report.json').is_file():
        from dotenv import dotenv_values
        for key,value in dotenv_values(root/'.env').items():
            if key in PATH_KEYS and value is not None:os.environ[key]=value
    from unmochon_live.config import Settings
    from unmochon_live.agentic_worker import bootstrap, resolve_local_model
    settings=Settings.load()
    spec={'package':str(root/'reference_pipelines/stage6'),
          'stage4_package':str(root/'reference_pipelines/stage4'),
          'registry':str(settings.research_registry),'workspace':str(settings.stage6_workspace),
          'model_cache':str(settings.stage6_model_cache or ''),'project':str(root)}
    bootstrap(spec)
    from stage6.generations import active
    from stage6.common import read,workspace_lock
    pointer=active(settings.stage6_workspace)
    state=read(settings.stage6_workspace/'workspace.json')
    model=resolve_local_model(spec)  # Original pinned hashes; offline only.
    assets=Assets(root)
    def path(key,default):
        p=Path(os.environ.get(key,default)).expanduser()
        return p if p.is_absolute() else root/p
    # Parent data asset first; child paths reuse its copy without duplication.
    assets.add('ORIGINAL_DATA_DIR',path('ORIGINAL_DATA_DIR','data'),'data/original')
    assets.paths.setdefault('ORIGINAL_DATA_DIR',root/'data')
    assets.add('STAGE6_WORKSPACE',settings.stage6_workspace,'data/stage6_workspace',True)
    assets.add('STAGE6_MODEL_PATH',model,'model_cache/embedding',True)
    for key,source,dest in [
        ('CORPUS_DIR',settings.corpus_dir,'data/corpus'),
        ('RAW_PDF_DIR',path('RAW_PDF_DIR',str(path('ORIGINAL_DATA_DIR','data')/'raw_pdfs')),'data/raw_pdfs'),
        ('DOC_METADATA_PATH',path('DOC_METADATA_PATH',str(path('ORIGINAL_DATA_DIR','data')/'doc_metadata.json')),'data/doc_metadata.json'),
        ('PROCESSED_DIR',path('PROCESSED_DIR',str(path('ORIGINAL_DATA_DIR','data')/'processed_jsonl')),'data/processed_jsonl'),
        ('CHROMADB_DIR',path('CHROMADB_DIR',str(path('ORIGINAL_DATA_DIR','data')/'chromedb')),'data/legacy_chromedb'),
        ('BM25_INDEX_PATH',path('BM25_INDEX_PATH',str(path('ORIGINAL_DATA_DIR','data')/'bm25_index.pkl')),'data/legacy_bm25_index.pkl'),
        ('STAGE2_EVIDENCE_DATA',path('STAGE2_EVIDENCE_DATA','data/stage2_evidence'),'data/stage2_evidence'),
        ('RESEARCH_OUTPUT_ROOT',settings.research_output_root,'data/research_runs'),
        ('SOURCE_REGISTRY',settings.source_registry,'config/sources.json'),
        ('RESEARCH_SOURCE_REGISTRY',settings.research_registry,'config/research_sources.json')]:
        assets.add(key,source,dest)
        assets.paths.setdefault(key,root/dest)
    old4=settings.stage4_package or root/'reference_pipelines/stage4'
    assets.add('STAGE4_OCR_MODELS',path('STAGE4_OCR_MODELS',str(old4/'models')),'model_cache/ocr')
    assets.paths.setdefault('STAGE4_OCR_MODELS',root/'model_cache/ocr')
    from stage4.pdf_processing import find_tesseract
    try:exe=Path(find_tesseract(settings.stage4_tesseract))
    except RuntimeError:exe=None
    if exe:
        if exe.resolve().is_relative_to(root.parent) and not exe.resolve().is_relative_to(root):
            assets.add('_tesseract_bin',exe.parent,'runtime/tesseract/bin',True)
            assets.paths['STAGE4_TESSERACT']=assets.paths.pop('_tesseract_bin')/exe.name
        else:assets.paths['STAGE4_TESSERACT']=exe.resolve()
    translation=os.environ.get('TRANSLATION_MODEL','facebook/nllb-200-distilled-600M')
    translation_path=path('TRANSLATION_MODEL',translation)
    if not translation_path.is_dir():
        try:
            from huggingface_hub import snapshot_download
            translation_path=Path(snapshot_download(translation,local_files_only=True))
        except Exception:translation_path=None
    if translation_path:
        assets.add('TRANSLATION_MODEL',translation_path,'model_cache/translation')
    return assets,settings,pointer,state,workspace_lock


def consolidate(root,apply=False,discovery=discover,check=None,model_check=None):
    root=Path(root).resolve()
    assets,settings,pointer,state,workspace_lock=discovery(root)
    pairs=assets.files()  # Validate every collision before any write.
    needed=sum(p.stat().st_size for p,d in pairs if not d.exists())
    if needed+32*1024*1024>shutil.disk_usage(root).free:
        raise ValueError('Insufficient free space for verified copies; no configuration changed')
    values={k:(v.relative_to(root).as_posix() if v.is_relative_to(root) else v.as_posix()) for k,v in assets.paths.items()}
    values.update(APP_ENV='local',RAG_BACKEND='stage6',ENABLE_WEB_SEARCH='false',
        STAGE4_PACKAGE='reference_pipelines/stage4',STAGE6_PACKAGE='reference_pipelines/stage6',
        STAGE6_MODEL_CACHE='model_cache',EMBED_MODEL=values['STAGE6_MODEL_PATH'],
        STAGE6_PYTHON=Path(sys.executable).as_posix(),HF_HOME='model_cache/huggingface',
        HF_HUB_CACHE='model_cache/huggingface/hub',HUGGINGFACE_HUB_CACHE='model_cache/huggingface/hub',
        TRANSFORMERS_CACHE='model_cache/huggingface/transformers',TORCH_HOME='model_cache/torch')
    values.setdefault('TRANSLATION_MODEL','facebook/nllb-200-distilled-600M')
    values.setdefault('STAGE4_TESSERACT','')
    external={k:v for k,v in values.items() if k in PATH_KEYS and k not in {'STAGE6_PYTHON','STAGE4_TESSERACT'}
              and (Path(v).is_absolute() and not Path(v).resolve().is_relative_to(root))}
    if external:raise ValueError('External runtime paths remain: '+', '.join(external))
    result={'status':'PLAN_ONLY','files_to_copy':sum(not d.exists() for _,d in pairs),
            'bytes_to_copy':needed,'active_generation':pointer['generation'],
            'sources_deleted':0,'index_rebuilt':False,'copies':[{'source':str(s),'destination':str(d)} for s,d in assets.copies]}
    if not apply:return result
    if check is None:
        from stage6.generations import active,verify_generation
        from run_stage2_live import resolve_model
        model_check=model_check or (lambda path:resolve_model(str(path),str(root/'model_cache')))
        def check(workspace):
            value=active(workspace)
            for ready in (Path(workspace)/'generations').glob('*/READY.json'):
                verify_generation(workspace,ready.parent.name)
            return value
    with workspace_lock(settings.stage6_workspace):
        print('Checking the active database and preserved generations...',flush=True)
        if check(settings.stage6_workspace)!=pointer:raise ValueError('Generation changed before copying')
        print('Copying and verifying',len(pairs),'existing files;',needed,'bytes to copy...',flush=True)
        for i,(source,dest) in enumerate(pairs,1):
            copy_verified(source,dest)
            if i%100==0:print('Verified copied files:',i,'/',len(pairs),flush=True)
        local=assets.paths['STAGE6_WORKSPACE']
        print('Checking the copied database and pinned local model...',flush=True)
        if check(local)!=pointer or check(settings.stage6_workspace)!=pointer:
            raise ValueError('Source/copy pointer differs; configuration was not changed')
        if model_check:model_check(assets.paths['STAGE6_MODEL_PATH'])
        stamp=datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')+'_'+uuid.uuid4().hex[:6]
        backup=root/'data/single_folder_backups'/stamp;backup.mkdir(parents=True)
        targets=[root/'.env',local/'workspace.json',root/'run_unmochon.py']
        previous={p:p.read_bytes() if p.exists() else None for p in targets}
        for i,(p,content) in enumerate(previous.items()):
            if content is not None:(backup/(str(i)+'_'+p.name+'.before')).write_bytes(content)
        new_state={**state,'model_path':str(assets.paths['STAGE6_MODEL_PATH']),'model_cache':str(root/'model_cache')}
        try:
            atomic_bytes(local/'workspace.json',json_bytes(new_state))
            atomic_bytes(root/'.env',env_bytes(previous[root/'.env'] or b'',values))
            atomic_bytes(root/'run_unmochon.py',LAUNCHER.encode('utf-8'))
            if check(local)!=pointer:raise ValueError('Final generation verification failed')
        except BaseException:
            for p,content in previous.items():
                if content is None:p.unlink(missing_ok=True)
                else:atomic_bytes(p,content)
            raise
    result.update(status='SINGLE_FOLDER_PASS',backup=str(backup),runtime_paths_local=True)
    lines=['# Unmochon single-folder check','', 'Status: SINGLE_FOLDER_PASS',
        'Active generation: '+pointer['generation'],'',
        'Run: `conda activate unmochon_stage1` then `python run_unmochon.py`.',
        '','## Folder cleanup','',
        'The sibling project/install folders below are not required by this app after these verified copies.',
        'They may contain old research reports, datasets, Git work, or benchmarks; retain those separately if wanted.',
        'This script has not deleted any folder. The Python/Conda environment remains required.','']
    for p in sorted(root.parent.iterdir(),key=lambda p:p.name.casefold()):
        if p.is_dir() and p!=root and (p.name.startswith('Unmochon') or p.name=='BD-Policy-RAG-System'):
            blocked=[k for k,v in values.items() if k in PATH_KEYS and Path(v).is_absolute() and Path(v).resolve().is_relative_to(p.resolve())]
            lines.append('- '+p.name+': '+('KEEP — runtime dependency '+', '.join(blocked) if blocked else 'NOT NEEDED TO RUN THIS APP'))
    lines += ['','Keep the complete `Unmochon` folder, especially data/, model_cache/, runtime/, reference_pipelines/, src/, scripts/, chatbot/, UI/, integrations/ and .env.',
              'Do not remove old folders unless this report says SINGLE_FOLDER_PASS. Historic audit records preserve original path strings; their contents are not rewritten.','']
    atomic_bytes(root/'FOLDER_CLEANUP_REPORT.md','\n'.join(lines).encode('utf-8'))
    atomic_bytes(root/'data/single_folder_report.json',json_bytes(result))
    return result


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root',type=Path,default=Path(__file__).resolve().parent)
    p.add_argument('--apply',action='store_true')
    args=p.parse_args()
    try:
        print(json.dumps(consolidate(args.root,args.apply),ensure_ascii=False,indent=2));return 0
    except Exception as error:
        print('BLOCKED: '+str(error),file=sys.stderr);return 2


if __name__=='__main__':raise SystemExit(main())
