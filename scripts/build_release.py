"""Build a deterministic source kit; generated vaults and local configs are excluded."""
from pathlib import Path
import hashlib
import json
import zipfile
import runpy

ROOT = Path(__file__).resolve().parents[1]
ALLOWED = ('README.md', 'LICENSE', '.gitignore', '.gitattributes', '.github/workflows/test.yml', 'skills/moss', 'tests', 'scripts/build_release.py', 'scripts/build_site.py', 'docs')


def main():
    files = []
    for rel in ALLOWED:
        path = ROOT / rel
        files.extend([path] if path.is_file() else [p for p in path.rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.suffix != '.pyc'])
    target = ROOT / 'dist'
    target.mkdir(exist_ok=True)
    version = runpy.run_path(str(ROOT / 'skills/moss/scripts/moss.py'))['VERSION']
    archive = target / ('moss-' + version + '.zip')
    manifest = []
    with zipfile.ZipFile(archive, 'w', compression=zipfile.ZIP_DEFLATED) as z:
        for path in sorted(files):
            rel = path.relative_to(ROOT).as_posix()
            data = path.read_bytes()
            info = zipfile.ZipInfo('moss/' + rel, date_time=(2026, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            z.writestr(info, data)
            manifest.append({'path': rel, 'sha256': hashlib.sha256(data).hexdigest()})
    (target / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')
    (target / 'SHA256SUMS.txt').write_text(hashlib.sha256(archive.read_bytes()).hexdigest() + '  ' + archive.name + '\n', encoding='utf-8')
    print(json.dumps({'archive': str(archive), 'files': len(manifest), 'bytes': archive.stat().st_size}))


if __name__ == '__main__':
    main()
