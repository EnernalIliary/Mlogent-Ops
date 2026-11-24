"""Build the tracked Ops distribution and SHA256SUMS.txt; no live-server access."""
from pathlib import Path
import hashlib
import subprocess
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]

def main():
    sys.path.insert(0, str(ROOT))
    from mlogent_ops import __version__
    dest = ROOT / 'dist' / ('v' + __version__)
    dest.mkdir(parents=True, exist_ok=True)
    files = subprocess.check_output(['git', 'ls-files', '-z'], cwd=ROOT).decode().split('\0')
    archive = dest / f'mlogent-ops-{__version__}.zip'
    with zipfile.ZipFile(archive, 'w', zipfile.ZIP_DEFLATED) as z:
        for rel in sorted(filter(None, files)):
            info = zipfile.ZipInfo(rel, (2026, 11, 24, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            z.writestr(info, (ROOT / rel).read_bytes())
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    (dest / 'SHA256SUMS.txt').write_text(f'{digest}  {archive.name}\n', encoding='utf-8')
    print(f'Built {archive} ({archive.stat().st_size} bytes)')

if __name__ == '__main__':
    main()
