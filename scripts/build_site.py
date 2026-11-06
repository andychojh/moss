"""Copy the standalone guide to the GitHub Pages publishing directory."""
from pathlib import Path
import argparse

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    source = ROOT / 'skills/moss/references/guide.ko.html'
    target = ROOT / 'docs/index.html'
    marker = ROOT / 'docs/.nojekyll'
    if args.check:
        if not target.exists() or target.read_bytes() != source.read_bytes() or not marker.exists():
            raise SystemExit('Site is stale. Run python scripts/build_site.py')
        print('Site matches the standalone guide.')
    else:
        target.parent.mkdir(exist_ok=True)
        target.write_bytes(source.read_bytes())
        marker.write_bytes(b'')
        print('Built docs/index.html from the standalone guide.')


if __name__ == '__main__':
    main()
