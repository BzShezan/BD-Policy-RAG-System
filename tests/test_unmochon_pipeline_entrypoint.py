import importlib.util
from pathlib import Path
import json
import pytest

SCRIPT = Path(__file__).resolve().parents[1]/'scripts'/'unmochon_pipeline.py'
spec=importlib.util.spec_from_file_location('unmochon_pipeline',SCRIPT)
module=importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


@pytest.fixture(autouse=True)
def isolate_runtime_environment(monkeypatch):
    # Original path imports load the real project's .env at collection time.
    # These inventory tests own temporary repositories, so they must not read
    # the user's live workspace through inherited shell/dotenv variables.
    for key in ('APP_ENV','RAG_BACKEND','ENABLE_WEB_SEARCH','STAGE4_PACKAGE',
                'STAGE6_PACKAGE','STAGE6_WORKSPACE','STAGE6_MODEL_CACHE'):
        monkeypatch.delenv(key,raising=False)


def fixture_repo(tmp_path):
    for path in ('src/unmochon_live/cli.py',*sum((list(x) for x in module.STAGES.values()), [])):
        p=tmp_path/path;p.parent.mkdir(parents=True,exist_ok=True);p.write_text('#test\n')
    return tmp_path


def test_all_six_stages_code_detected(tmp_path):
    repo=fixture_repo(tmp_path)
    data=module.inventory(repo)
    assert set(data['stages'])=={f'stage{i}' for i in range(1,7)}
    assert all(row['code_present'] for row in data['stages'].values())
    assert data['index_writes']==data['network_calls']==0


def test_untrusted_pointer_does_not_activate_or_write(tmp_path):
    repo=fixture_repo(tmp_path)
    ws=repo/'workspace';ws.mkdir();(ws/'active.json').write_text(json.dumps({'generation':'sealed_original'}))
    (repo/'.env').write_text('APP_ENV=local\nRAG_BACKEND=stage6\nENABLE_WEB_SEARCH=false\nSTAGE6_WORKSPACE=workspace\n')
    before=(ws/'active.json').read_bytes()
    out=module.inventory(repo)
    assert out['active_pointer_generation_unverified']=='sealed_original'
    assert (ws/'active.json').read_bytes()==before


def test_runtime_refuses_missing_guard(tmp_path):
    repo=fixture_repo(tmp_path)
    (repo/'.env').write_text('APP_ENV=local\nRAG_BACKEND=original\nENABLE_WEB_SEARCH=true\n')
    try:
        module.safe_runtime(repo)
    except RuntimeError:
        pass
    else:
        raise AssertionError('Should refuse original/web fallback mode')


def test_subcommands_are_registered():
    parser=module.build_parser()
    for subcmd in ['doctor','test','serve']:
        assert parser.parse_args([subcmd]).command==subcmd


def test_config_does_not_leak_secrets(tmp_path):
    f=tmp_path/'.env';f.write_text('APP_ENV=local\nOPENROUTER_API_KEY=private\nSTAGE6_PACKAGE=hello\n')
    assert 'OPENROUTER_API_KEY' not in module.read_known_env(f)


def test_explicit_environment_override_is_preserved(tmp_path,monkeypatch):
    f=tmp_path/'.env'
    f.write_text('STAGE6_WORKSPACE=file-selected\n',encoding='utf-8')
    monkeypatch.setenv('STAGE6_WORKSPACE','environment-selected')
    assert module.read_known_env(f)['STAGE6_WORKSPACE']=='environment-selected'
