"""Trusted execution controller, copied into the runner image (not generated)."""
import json
from pathlib import Path
import subprocess
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


def execute():
    syntax_error = syntax_check(Path('/workspace'))
    if syntax_error:
        return syntax_error
    report = dict(status='FAILED', detail='', exit_code=None, collected=0, passed=0, failed=0, skipped=0, startup_ok=False)
    with open('/tmp/tests.log', 'w') as output:
        result = subprocess.run(['python', '-m', 'pytest', 'tests', '-q', '-p', 'no:cacheprovider',
                                 '--junitxml=/tmp/results.xml'], stdout=output, stderr=subprocess.STDOUT, timeout=60)
    report['exit_code'] = result.returncode
    report['detail'] = Path('/tmp/tests.log').read_text(errors='replace')[-12000:]
    if Path('/tmp/results.xml').exists():
        root = ET.parse('/tmp/results.xml').getroot()
        suites = [root] if root.tag == 'testsuite' else list(root.iter('testsuite'))
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
