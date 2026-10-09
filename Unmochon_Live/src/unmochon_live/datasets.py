"""Offline dataset updates: validate, stage, then commit with a recoverable backup."""
import json
import os
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from filelock import FileLock, Timeout

SUFFIXES = ('_clauses.jsonl', '_clauses_review.jsonl', '_tables.jsonl')
MINISTRIES = ('Social_Welfare', 'Agriculture', 'Disaster_Management')

def validate_dataset(folder, metadata=None):
    folder = Path(folder).resolve()
    files = sorted(folder.glob('*.jsonl'))
    if not files:
        raise ValueError('Dataset folder contains no JSONL files.')
    seen_chunks = set()
    for path in files:
        if not path.name.endswith(SUFFIXES) or not path.name.startswith(tuple(m + '_' for m in MINISTRIES)):
            raise ValueError(f'Use original ministry filenames, e.g. Agriculture_clauses.jsonl: {path.name}')
        seen = set()
        for number, line in enumerate(path.read_text(encoding='utf-8-sig').splitlines(), 1):
            if not line.strip(): continue
            try: row = json.loads(line)
            except ValueError as exc: raise ValueError(f'{path.name}:{number}: invalid JSON') from exc
            if not isinstance(row, dict) or not row.get('doc_id') or not isinstance(row.get('page_number'), int) or isinstance(row.get('page_number'), bool) or row['page_number'] < 1:
                raise ValueError(f'{path.name}:{number}: doc_id and positive page_number are required.')
            field = 'raw_text' if path.name.endswith('_tables.jsonl') else 'text'
            if not isinstance(row.get(field), str) or not row[field].strip():
                raise ValueError(f'{path.name}:{number}: nonempty {field} is required.')
            if field == 'text':
                if not row.get('clause_id') or not isinstance(row.get('quality_score'), (float, int)):
                    raise ValueError(f'{path.name}:{number}: clause_id and quality_score are required.')
                if row['clause_id'] in seen_chunks: raise ValueError(f'{path.name}:{number}: duplicate clause_id')
                seen_chunks.add(row['clause_id'])
    if metadata:
        data = json.loads(Path(metadata).read_text(encoding='utf-8-sig'))
        if not isinstance(data, dict) or any(not isinstance(v, dict) for v in data.values()):
            raise ValueError('Metadata must be a doc_id -> object map, matching original doc_metadata.json.')
    return files

def update_dataset(folder, metadata=None, worker=None):
    from original_paths import PROJECT_ROOT, CHROMADB_DIR, BM25_INDEX_PATH, METADATA_PATH, DATA_DIR, PROCESSED_DIR
    files = validate_dataset(folder, metadata)
    if not (Path(CHROMADB_DIR) / 'chroma.sqlite3').exists():
        raise ValueError('Existing original ChromaDB is missing. Refusing to create a different database.')
    lock = FileLock(str(PROJECT_ROOT / '.database.lock'), timeout=0)
    try: lock.acquire()
    except Timeout as exc: raise RuntimeError('Stop the running search server/CLI before updating its dataset.') from exc
    try:
        stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
        stage = Path(tempfile.mkdtemp(prefix='unmochon-update-', dir=DATA_DIR))
        staged_db, staged_index, staged_meta = stage/'chromedb', stage/'bm25_index.pkl', stage/'doc_metadata.json'
        shutil.copytree(CHROMADB_DIR, staged_db)
        shutil.copy2(BM25_INDEX_PATH, staged_index)
        if METADATA_PATH.exists(): shutil.copy2(METADATA_PATH, staged_meta)
        else: staged_meta.write_text('{}', encoding='utf-8')
        dataset_copy = stage/'dataset'; dataset_copy.mkdir()
        for path in files: shutil.copy2(path, dataset_copy/path.name)
        if metadata: shutil.copy2(metadata, stage/'incoming_metadata.json')
        report_path = stage/'update_report.json'
        env = {**os.environ, 'UNMOCHON_HOME': str(PROJECT_ROOT), 'CHROMADB_DIR':str(staged_db),
               'BM25_INDEX_PATH':str(staged_index), 'DOC_METADATA_PATH':str(staged_meta),
               'UPDATE_REPORT_PATH':str(report_path)}
        command = [sys.executable, '-m', 'unmochon_live.dataset_worker', str(dataset_copy)]
        if metadata: command.append(str(stage/'incoming_metadata.json'))
        try:
            (worker or subprocess.run)(command, env=env, check=True, cwd=PROJECT_ROOT)
            report = json.loads(report_path.read_text(encoding='utf-8'))
            # Worker exited; all SQLite/HNSW handles have closed before directory replacement.
            backup = DATA_DIR/'update_backups'/stamp; backup.mkdir(parents=True)
            # Merge original JSONL sources by clause id (or original table row id), retaining other records.
            jsonl_operations = []
            touched = {}
            for path in files:
                ministry = next(m for m in MINISTRIES if path.name.startswith(m + '_'))
                suffix = next(s for s in sorted(SUFFIXES, key=len, reverse=True) if path.name.endswith(s))
                target = Path(PROCESSED_DIR) / (ministry + suffix)
                rows = touched.setdefault(target, {})
                def identity(row):
                    return row.get('clause_id') or row.get('table_row_id') or (row.get('doc_id'), row.get('page_number'), row.get('table_index'), row.get('row_index'))
                if target.exists() and not rows:
                    for line in target.read_text(encoding='utf-8').splitlines():
                        if line.strip():
                            row = json.loads(line); rows[identity(row)] = row
                for line in path.read_text(encoding='utf-8-sig').splitlines():
                    if line.strip():
                        row = json.loads(line)
                        rows[identity(row)] = {**rows.get(identity(row), {}), **row}
            for target, rows in touched.items():
                source = stage / ('merged-' + target.name)
                source.write_text(''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in rows.values()), encoding='utf-8')
                jsonl_operations.append((target, source, backup / target.name))
            operations = [(Path(CHROMADB_DIR), staged_db, backup/'chromedb'),
                          (Path(BM25_INDEX_PATH), staged_index, backup/'bm25_index.pkl'),
                          (METADATA_PATH, staged_meta, backup/'doc_metadata.json')] + jsonl_operations
            # Paths can be configured on another filesystem, so copy into each target's parent first.
            prepared = []
            for target, source, saved in operations:
                target.parent.mkdir(parents=True, exist_ok=True)
                incoming = target.with_name(target.name + '.incoming-' + stamp)
                if source.is_dir(): shutil.copytree(source, incoming)
                else: shutil.copy2(source, incoming)
                if target.exists():
                    if target.is_dir(): shutil.copytree(target, saved)
                    else: shutil.copy2(target, saved)
                prepared.append((target, incoming, saved))
            replaced = []
            try:
                for target, incoming, saved in prepared:
                    replaced.append((target, saved))
                    if target.is_dir(): shutil.rmtree(target)
                    os.replace(incoming, target)
            except BaseException:
                for target, saved in reversed(replaced):
                    if target.is_dir(): shutil.rmtree(target)
                    elif target.exists(): target.unlink()
                    if saved.is_dir(): shutil.copytree(saved, target)
                    elif saved.exists(): shutil.copy2(saved, target)
                raise
            shutil.copytree(dataset_copy, backup/'dataset')
            report['backup'] = str(backup)
            (backup/'report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
            (DATA_DIR/'last_update.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
            return report
        finally:
            shutil.rmtree(stage, ignore_errors=True)
    finally:
        lock.release()
