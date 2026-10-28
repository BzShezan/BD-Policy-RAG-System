"""Hash-checked code installer. Dry-run by default; never installs runtime data.

Used as install_integration.py beside patch_manifest.json and payload/ in the ZIP.
All target files are checked before any mutation. Existing code is backed up;
ordinary write failures restore the complete pre-install state.
"""
from __future__ import annotations
import argparse
from datetime import datetime,timezone
import hashlib
import json
import os
from pathlib import Path,PurePosixPath
import shutil
import sys
import uuid


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def safe(root,name):
    rel=PurePosixPath(name)
    if rel.is_absolute() or '..' in rel.parts or not rel.parts:
        raise ValueError('Unsafe package path')
    destination=root.joinpath(*rel.parts)
    if not destination.resolve().is_relative_to(root.resolve()):
        raise ValueError('Target escapes the project')
    if any(p.is_symlink() for p in (destination,*destination.parents) if p==root or root in p.parents):
        raise ValueError('Symlinked installation path')
    return destination


def atomic_copy(source,destination):
    destination.parent.mkdir(parents=True,exist_ok=True)
    temp=destination.with_name('.'+destination.name+'.'+uuid.uuid4().hex+'.tmp')
    try:
        shutil.copy2(source,temp)
        os.replace(temp,destination)
    finally: temp.unlink(missing_ok=True)


def inspect(package,target):
    package,target=Path(package).resolve(),Path(target).resolve()
    manifest=json.loads((package/'patch_manifest.json').read_text(encoding='utf-8'))
    if manifest.get('schema_version')!=1:raise ValueError('Unknown patch format')
    if not (target/'src/unmochon_live/cli.py').is_file():
        raise ValueError('Target is not the existing unified Unmochon project')
    changes=[]
    for name,info in manifest['files'].items():
        if name=='.env' or name.startswith(('data/','model_cache/')):
            raise ValueError('Runtime data or secrets cannot be installed by a code patch')
        src=safe(package/'payload',name);dst=safe(target,name)
        if not src.is_file() or sha(src)!=info['after_sha256']:
            raise ValueError('Patch payload integrity failed: '+name)
        actual=sha(dst) if dst.is_file() else None
        if actual==info['after_sha256']:continue
        if actual!=info['before_sha256']:
            raise ValueError('Unexpected local change; nothing installed: '+name)
        changes.append((name,src,dst,actual))
    for name,expected in manifest.get('required_original_sources',{}).items():
        src=safe(target,name)
        if not src.is_file() or sha(src)!=expected:
            raise ValueError('Borrowed Stage source is missing or changed: '+name)
    return manifest,changes


def install(package,target,apply=False,writer=atomic_copy):
    package,target=Path(package).resolve(),Path(target).resolve()
    manifest,changes=inspect(package,target)
    report={'status':'DRY_RUN_PASS','files_to_change':[n for n,*_ in changes],
            'already_installed':len(manifest['files'])-len(changes),
            'runtime_assets_changed':False,'index_writes':0}
    if not apply or not changes:return report
    lock=target/'.integration_install.lock'
    with lock.open('x') as stream:stream.write(str(os.getpid()))
    try:
        # Recheck after acquiring the installer lock, before copying any file.
        manifest,changes=inspect(package,target)
        backup=target/'data/integration_backups'/('agentic_'+datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')+'_'+uuid.uuid4().hex[:6])
        backup.mkdir(parents=True,exist_ok=False)
        records=[]
        for name,src,dst,previous in changes:
            if previous is not None:
                saved=safe(backup/'files',name);saved.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(dst,saved)
            records.append({'path':name,'before_sha256':previous,'after_sha256':sha(src)})
        (backup/'backup_manifest.json').write_text(json.dumps({'target':str(target),'files':records},indent=2)+'\n')
        attempted=[]
        try:
            for name,src,dst,previous in changes:
                attempted.append((name,dst,previous))
                writer(src,dst)
                if sha(dst)!=sha(src):raise ValueError('Written file hash mismatch: '+name)
        except Exception:
            for name,dst,previous in reversed(attempted):
                if previous is None:dst.unlink(missing_ok=True)
                else:atomic_copy(safe(backup/'files',name),dst)
            raise
        report.update(status='APPLIED',backup=str(backup))
        (backup/'install_report.json').write_text(json.dumps(report,indent=2)+'\n')
        return report
    finally:lock.unlink(missing_ok=True)


def restore(target,backup,apply=False):
    target,backup=Path(target).resolve(),Path(backup).resolve()
    record=json.loads((backup/'backup_manifest.json').read_text())
    if Path(record['target']).resolve()!=target:raise ValueError('Backup belongs to a different target')
    for item in record['files']:
        dst=safe(target,item['path'])
        if not dst.is_file() or sha(dst)!=item['after_sha256']:
            raise ValueError('Code changed after installation; restore refused: '+item['path'])
        if item['before_sha256'] is not None and sha(safe(backup/'files',item['path']))!=item['before_sha256']:
            raise ValueError('Backup hash mismatch')
    if apply:
        for item in record['files']:
            dst=safe(target,item['path'])
            if item['before_sha256'] is None:dst.unlink()
            else:atomic_copy(safe(backup/'files',item['path']),dst)
    return {'status':'RESTORED' if apply else 'RESTORE_DRY_RUN_PASS','index_writes':0}


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--target',type=Path,required=True)
    p.add_argument('--package',type=Path,default=Path(__file__).resolve().parent)
    p.add_argument('--apply',action='store_true')
    p.add_argument('--restore',type=Path)
    args=p.parse_args(argv)
    try:
        result=restore(args.target,args.restore,args.apply) if args.restore else install(args.package,args.target,args.apply)
        print(json.dumps(result,ensure_ascii=False,indent=2));return 0
    except (ValueError,OSError,KeyError) as exc:
        print('BLOCKED: '+str(exc),file=sys.stderr);return 2


if __name__=='__main__':raise SystemExit(main())
