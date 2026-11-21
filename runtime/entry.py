"""Trusted execution controller, copied into the runner image (not generated)."""
import ast
import json
from pathlib import Path
import subprocess
import sys
import time
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET


def syntax_check(root):
    for path in [root / 'app.py', root / 'logic.py', *sorted((root / 'tests').glob('test_*.py'))]:
        try:
            compile(path.read_text(), str(path), 'exec')
        except SyntaxError as exc:
            return dict(status='ERROR' if path.parent.name == 'tests' else 'FAILED',
                        detail=f'{path.name}:{exc.lineno}: {exc.msg}')
    return None


def application_import_error(root, log_path, expected_callbacks=()):
    probe = (
        'import app, sys\n'
        'missing = [name for name in sys.argv[1:] if not callable(getattr(app, name, None))]\n'
        'if missing:\n'
        '    raise ImportError("Missing callable app exports required by tests: " + ", ".join(missing))'
    )
    with log_path.open('w') as output:
        try:
            result = subprocess.run([sys.executable, '-c', probe, *expected_callbacks], cwd=root,
                                    stdout=output, stderr=subprocess.STDOUT, timeout=15)
        except subprocess.TimeoutExpired:
            return ('Importing app.py exceeded 15 seconds. Importing app must return without '
                    'starting a server or running other blocking work.\n'
                    + log_path.read_text(errors='replace')[-4000:])
    if result.returncode != 0:
        return log_path.read_text(errors='replace')[-4000:]
    return None


def execute():
    root = Path('/workspace')
    syntax_error = syntax_check(root)
    if syntax_error:
        return syntax_error
    callbacks = {
        alias.name
        for path in (root / 'tests').glob('test_*.py')
        for node in ast.walk(ast.parse(path.read_bytes()))
        if isinstance(node, ast.ImportFrom) and node.level == 0 and node.module == 'app'
        for alias in node.names
    }
    import_error = application_import_error(root, Path('/tmp/app-import.log'), sorted(callbacks))
    if import_error is not None:
        return dict(status='FAILED', detail='Application import check failed before pytest:\n' + import_error)
    report = dict(status='FAILED', detail='', exit_code=None, collected=0, passed=0, failed=0, skipped=0, startup_ok=False)
    with open('/tmp/tests.log', 'w') as output:
        try:
            result = subprocess.run(['python', '-m', 'pytest', 'tests', '-q', '-p', 'no:cacheprovider',
                                     '--junitxml=/tmp/results.xml'], stdout=output, stderr=subprocess.STDOUT, timeout=60)
        except subprocess.TimeoutExpired:
            return dict(status='ERROR', detail='pytest exceeded 60 seconds after the application import check passed.\n'
                        + Path('/tmp/tests.log').read_text(errors='replace')[-12000:])
    report['exit_code'] = result.returncode
    report['detail'] = Path('/tmp/tests.log').read_text(errors='replace')[-12000:]
    if Path('/tmp/results.xml').exists():
        xml_root = ET.parse('/tmp/results.xml').getroot()
        suites = [xml_root] if xml_root.tag == 'testsuite' else list(xml_root.iter('testsuite'))
        report['collected'] = sum(int(s.get('tests', 0)) for s in suites)
        report['failed'] = sum(int(s.get('failures', 0)) + int(s.get('errors', 0)) for s in suites)
        report['skipped'] = sum(int(s.get('skipped', 0)) for s in suites)
        report['passed'] = report['collected'] - report['failed'] - report['skipped']
    if result.returncode in (2, 3, 4, 5) or report['collected'] == 0 or report['skipped']:
        report['status'] = 'ERROR'
        report['detail'] += '\nTest collection/infrastructure error or skipped tests; application repair not attempted.'
        return report
    if result.returncode != 0:
        return report
    with open('/tmp/app.log', 'w') as output:
        app = subprocess.Popen(['python', 'app.py'], stdout=output, stderr=subprocess.STDOUT)
        try:
            for _ in range(60):
                if app.poll() is not None:
                    break
                try:
                    with urllib.request.urlopen('http://127.0.0.1:7860', timeout=1) as response:
                        if response.status == 200:
                            report['startup_ok'] = True
                            report['status'] = 'PASSED'
                            break
                except (urllib.error.URLError, TimeoutError):
                    time.sleep(0.5)
        finally:
            if app.poll() is None:
                app.terminate()
                try:
                    app.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    app.kill()
                    app.wait()
    if not report['startup_ok']:
        report['detail'] += '\nApp startup failed:\n' + Path('/tmp/app.log').read_text(errors='replace')[-8000:]
    return report


if __name__ == '__main__':
    try:
        report = execute()
    except (subprocess.TimeoutExpired, OSError, ET.ParseError) as exc:
        report = dict(status='ERROR', detail=f'Execution infrastructure error: {type(exc).__name__}')
    print(json.dumps(report), flush=True)
