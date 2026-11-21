from pathlib import Path
import subprocess
from types import SimpleNamespace
import pytest
from ai_coder.runner import DockerRunner
from runtime.entry import application_import_error, syntax_check


def test_syntax_errors_are_attributed_without_executing(tmp_path):
    (tmp_path / 'app.py').write_text('def broken(:')
    (tmp_path / 'logic.py').write_text('x = 1')
    assert syntax_check(tmp_path)['status'] == 'FAILED'
    (tmp_path / 'app.py').write_text('raise RuntimeError("must not execute")')
    (tmp_path / 'tests').mkdir()
    (tmp_path / 'tests/test_x.py').write_text('def broken(:')
    assert syntax_check(tmp_path)['status'] == 'ERROR'


def test_application_import_check_does_not_load_pytest_files(tmp_path):
    app = tmp_path / 'app.py'
    log = tmp_path / 'app-import.log'
    test_dir = tmp_path / 'tests'
    test_dir.mkdir()
    (test_dir / 'test_invalid.py').write_text('raise RuntimeError("test-side error")')
    app.write_text('pass')
    assert application_import_error(tmp_path, log) is None

    app.write_text('raise TypeError("invalid application constructor argument")')
    assert 'TypeError: invalid application constructor argument' in application_import_error(tmp_path, log)


def test_application_import_timeout_reports_blocked_import(monkeypatch, tmp_path):
    def blocked_import(command, **kwargs):
        raise subprocess.TimeoutExpired(command, kwargs['timeout'])

    monkeypatch.setattr('runtime.entry.subprocess.run', blocked_import)
    detail = application_import_error(tmp_path, tmp_path / 'app-import.log')
    assert 'Importing app.py exceeded 15 seconds' in detail
    assert 'starting a server' in detail


def test_application_import_reports_missing_callback(tmp_path):
    (tmp_path / 'app.py').write_text('def randomize_callback():\n    return "ok"')
    log = tmp_path / 'app-import.log'
    assert application_import_error(tmp_path, log, ['randomize_callback']) is None
    assert 'Missing callable app exports required by tests: reshuffle_callback' in (
        application_import_error(tmp_path, log, ['randomize_callback', 'reshuffle_callback'])
    )


def test_container_never_inherits_model_secret(tmp_path):
    args = DockerRunner.restrictions(tmp_path)
    assert '--read-only' in args
    assert '--cap-drop=ALL' in args
    assert 'readonly' in args[-1]
    assert not any('GEMINI' in arg for arg in args)


def test_runner_unavailable_is_explicit(monkeypatch, tmp_path):
    runner = DockerRunner()
    monkeypatch.setattr(runner, 'check', lambda: 'not available')
    result = runner.run(tmp_path)
    assert result.status == 'NOT RUN'
    assert not result.startup_ok


def test_single_log_file_disables_docker_compression(tmp_path):
    assert '--log-opt=compress=false' in DockerRunner.restrictions(tmp_path)


def test_report_is_read_from_persistent_container_logs(monkeypatch, tmp_path):
    import json
    from types import SimpleNamespace
    report = {'status':'PASSED','detail':'one test','collected':1,'passed':1,'startup_ok':True}
    def command(*args, **kwargs):
        return SimpleNamespace(returncode=0, stderr='', stdout=json.dumps(report) if args[0]=='logs' else '0')
    monkeypatch.setattr('ai_coder.runner.docker', command)
    runner = DockerRunner()
    monkeypatch.setattr(runner, 'check', lambda: None)
    assert runner.run(tmp_path).status == 'PASSED'


def test_preview_uses_approved_bridge_and_loopback_only(monkeypatch, tmp_path):
    from types import SimpleNamespace
    calls = []
    def command(*args, **kwargs):
        calls.append(args)
        if args[0] == 'inspect':
            return SimpleNamespace(returncode=0, stdout='true', stderr='')
        return SimpleNamespace(returncode=0, stdout='127.0.0.1:34567\n' if args[0]=='port' else 'container', stderr='')
    monkeypatch.setattr('ai_coder.runner.docker', command)
    runner = DockerRunner()
    monkeypatch.setattr(runner, 'check', lambda: None)
    from unittest.mock import MagicMock
    opener = MagicMock()
    opener.open.return_value.__enter__.return_value.status = 200
    monkeypatch.setattr('ai_coder.runner.urllib.request.build_opener', lambda *args: opener)
    name, url = runner.preview(tmp_path)
    opener.open.assert_called_once_with('http://127.0.0.1:34567', timeout=1)
    start = next(c for c in calls if c[0]=='run')
    assert start[start.index('--network')+1] == 'bridge'
    assert start[start.index('-p')+1] == '127.0.0.1::7860'
    assert url == 'http://127.0.0.1:34567'


def test_runtime_disables_browser_history(tmp_path):
    assert '--env=GRADIO_RUN_HISTORY=False' in DockerRunner.restrictions(tmp_path)


def test_preview_failure_includes_logs_and_removes_container(monkeypatch, tmp_path):
    calls = []

    def command(*args, **kwargs):
        calls.append(args)
        output = {'port': '127.0.0.1:34567', 'inspect': 'false', 'logs': 'App startup traceback'}
        return SimpleNamespace(returncode=0, stdout=output.get(args[0], ''), stderr='')

    monkeypatch.setattr('ai_coder.runner.docker', command)
    runner = DockerRunner()
    monkeypatch.setattr(runner, 'check', lambda: None)
    with pytest.raises(RuntimeError, match='App startup traceback'):
        runner.preview(tmp_path)
    assert calls[-1][0:2] == ('rm', '-f')


def test_cleanup_timeout_does_not_hide_execution_failure(monkeypatch, tmp_path):
    def command(*args, **kwargs):
        if args[0] == 'rm':
            raise subprocess.TimeoutExpired(args, 15)
        return SimpleNamespace(returncode=1, stdout='', stderr='Original Docker failure')

    monkeypatch.setattr('ai_coder.runner.docker', command)
    runner = DockerRunner()
    monkeypatch.setattr(runner, 'check', lambda: None)
    assert runner.run(tmp_path).detail == 'Original Docker failure'


def test_preview_retries_until_http_ready(monkeypatch, tmp_path):
    from unittest.mock import MagicMock
    import urllib.error

    def command(*args, **kwargs):
        output = {'port': '127.0.0.1:34567', 'inspect': 'true'}
        return SimpleNamespace(returncode=0, stdout=output.get(args[0], ''), stderr='')

    opener = MagicMock()
    response = MagicMock()
    response.__enter__.return_value.status = 200
    opener.open.side_effect = [urllib.error.URLError('Connection refused'), response]
    monkeypatch.setattr('ai_coder.runner.docker', command)
    monkeypatch.setattr('ai_coder.runner.urllib.request.build_opener', lambda *args: opener)
    monkeypatch.setattr('ai_coder.runner.time.sleep', lambda seconds: None)
    runner = DockerRunner()
    monkeypatch.setattr(runner, 'check', lambda: None)
    assert runner.preview(tmp_path)[1] == 'http://127.0.0.1:34567'
    assert opener.open.call_count == 2


def test_preview_timeout_cleans_up(monkeypatch, tmp_path):
    calls = []

    def command(*args, **kwargs):
        calls.append(args)
        return SimpleNamespace(returncode=0, stdout='127.0.0.1:34567' if args[0] == 'port' else '', stderr='')

    clock = iter([0, 31])
    monkeypatch.setattr('ai_coder.runner.time.monotonic', lambda: next(clock))
    monkeypatch.setattr('ai_coder.runner.docker', command)
    runner = DockerRunner()
    monkeypatch.setattr(runner, 'check', lambda: None)
    with pytest.raises(RuntimeError, match='30 seconds'):
        runner.preview(tmp_path)
    assert calls[-1][0:2] == ('rm', '-f')
