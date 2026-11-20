import hashlib
import json
import re
import zipfile
from pathlib import Path

DEPENDENCIES = 'gradio==6.32.0\npytest==9.2.0\n'
RUNTIME_GUIDE = '''# Runtime setup (provided by AI Coder)

Use Python 3.14+ and the supplied fixed dependencies. Launch without saving player inputs in Gradio browser history:

```sh
python -m pip install -r requirements.txt
export GRADIO_RUN_HISTORY=False
export GRADIO_ANALYTICS_ENABLED=False
python app.py
```

Run tests with `python -m pytest tests`. For untrusted output, use the AI Coder Docker runner rather than executing on your host.

---

'''



class Workspace:
    def __init__(self, root: Path):
        self.root = root
        self.generated = root / 'generated'
        self.generated.mkdir(parents=True, exist_ok=True)
        (self.generated / 'requirements.txt').write_text(DEPENDENCIES)
        self.paths = {'requirements.txt'}

    def save(self, name, value):
        (self.root / name).write_text(json.dumps(value, indent=2), encoding='utf-8')

    def write_files(self, files, role):
        names = [f.path for f in files]
        if len(set(names)) != len(names) or sum(len(f.content.encode()) for f in files) > 400000:
            raise ValueError('Duplicate files or oversized artifacts')
        for name in names:
            allowed = name in {'app.py', 'logic.py', 'README.md'} if role == 'developer' else bool(re.fullmatch(r'tests/test_[a-zA-Z0-9_]+\.py', name))
            if not allowed:
                raise ValueError(f'Forbidden artifact path: {name}')
        if role == 'tester':
            for name in list(self.paths):
                if name.startswith('tests/'):
                    (self.generated / name).unlink()
                    self.paths.remove(name)
        for file in files:
            target = self.generated / file.path
            target.parent.mkdir(parents=True, exist_ok=True)
            content = RUNTIME_GUIDE + file.content if file.path == 'README.md' else file.content
            target.write_text(content, encoding='utf-8')
            self.paths.add(file.path)

    def hashes(self):
        return {p: hashlib.sha256((self.generated / p).read_bytes()).hexdigest() for p in sorted(self.paths)}

    def export(self, status, manual_ui_validation='NOT RUN'):
        self.save('manifest.json', {'status': status, 'files': self.hashes(),
                                   'manual_ui_validation': manual_ui_validation})
        bundle = self.root / 'project.zip'
        with zipfile.ZipFile(bundle, 'w', zipfile.ZIP_DEFLATED) as archive:
            for name in sorted(self.paths):
                archive.write(self.generated / name, name)
            for name in ('request.json', 'spec.json', 'coverage.json', 'reports.json', 'usage.json', 'trace.json', 'manifest.json', 'rules.json', 'result.json', 'rejected_tests.json', 'runtime-verification.json', 'interaction-checks.json', 'browser-verification.json', 'browser-preview.jpg'):
                if (self.root / name).exists():
                    archive.write(self.root / name, name)
        return bundle
