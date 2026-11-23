"""Run standalone policy/recorder tests; never connects to the live server."""
from pathlib import Path
import subprocess
import sys

root = Path(__file__).resolve().parents[1]
failed = []
for path in sorted((root/'tests/world').glob('run_*_tests.py')):
    result = subprocess.run([sys.executable, str(path)], cwd=root)
    if result.returncode:
        failed.append(path.name)
if failed:
    raise SystemExit('Failed: '+', '.join(failed))
print('Mlogent-Ops standalone checks passed')
