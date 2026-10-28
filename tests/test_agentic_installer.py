"""Code installation safety and backup/restore tests, independent of runtime data."""
import hashlib
import json
from pathlib import Path
import pytest
from scripts.install_agentic_patch import install,restore,atomic_copy
from scripts.configure_agentic import parse_env


def package(tmp):
    target=tmp/'target';bundle=tmp/'package'
    (target/'src/unmochon_live').mkdir(parents=True)
    (target/'src/unmochon_live/cli.py').write_text('existing entrypoint')
    (target/'old.py').write_bytes(b'old\r\n')
    (target/'data').mkdir();(target/'data/active.json').write_text('must not change')
    (bundle/'payload').mkdir(parents=True)
    (bundle/'payload/old.py').write_bytes(b'new\n')
    (bundle/'payload/new.py').write_bytes(b'new module\n')
    def sha(b):return hashlib.sha256(b).hexdigest()
    (bundle/'patch_manifest.json').write_text(json.dumps({'schema_version':1,'files':{
        'old.py':{'before_sha256':sha(b'old\r\n'),'after_sha256':sha(b'new\n')},
        'new.py':{'before_sha256':None,'after_sha256':sha(b'new module\n')}},'required_original_sources':{}}))
    return bundle,target


def test_dry_run_apply_idempotency_restore(tmp_path):
    bundle,target=package(tmp_path)
    assert install(bundle,target)['status']=='DRY_RUN_PASS'
    assert (target/'old.py').read_bytes()==b'old\r\n' and not (target/'new.py').exists()
    result=install(bundle,target,True)
    assert result['status']=='APPLIED'
    assert install(bundle,target,True)['already_installed']==2
    assert (target/'data/active.json').read_text()=='must not change'
    backup=Path(result['backup'])
    assert restore(target,backup)['status']=='RESTORE_DRY_RUN_PASS'
    assert restore(target,backup,True)['status']=='RESTORED'
    assert (target/'old.py').read_bytes()==b'old\r\n' and not (target/'new.py').exists()


def test_unexpected_edits_refused_before_any_write(tmp_path):
    bundle,target=package(tmp_path)
    (target/'old.py').write_text('uncommitted work')
    with pytest.raises(ValueError,match='Unexpected local change'):install(bundle,target,True)
    assert not (target/'new.py').exists()
    assert not (target/'data/integration_backups').exists()


def test_corrupted_payload_refused(tmp_path):
    bundle,target=package(tmp_path)
    (bundle/'payload/new.py').write_text('tampered')
    with pytest.raises(ValueError,match='payload integrity'):install(bundle,target,True)
    assert (target/'old.py').read_bytes()==b'old\r\n'


def test_interrupted_install_restores_every_attempted_file(tmp_path):
    bundle,target=package(tmp_path)
    calls=[]
    def broken_writer(src,dst):
        calls.append(dst)
        atomic_copy(src,dst)
        if len(calls)==2:raise OSError('Injected failure after second replacement')
    with pytest.raises(OSError):install(bundle,target,True,writer=broken_writer)
    assert (target/'old.py').read_bytes()==b'old\r\n' and not (target/'new.py').exists()
    assert not (target/'.integration_install.lock').exists()


def test_restore_refuses_later_user_edits(tmp_path):
    bundle,target=package(tmp_path)
    report=install(bundle,target,True)
    (target/'new.py').write_text('later user work')
    with pytest.raises(ValueError,match='Code changed'):restore(target,report['backup'],True)
    assert (target/'old.py').read_bytes()==b'new\n'


def test_environment_parser_preserves_values_without_printing_secrets(tmp_path):
    path=tmp_path/'env'
    path.write_text('# comment\nSTAGE6_PACKAGE="G:/old/stage6"\nGEMINI_API_KEY=synthetic-test-secret\n')
    env=parse_env(path)
    assert env['STAGE6_PACKAGE']=='G:/old/stage6'
    assert len(env)==2
