"""Existing-vault migration: inspect, prepare a complete copy, then activate it.

No source vault is changed by audit or prepare. Python 3.10+, standard library.
"""
import argparse
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import tempfile
from urllib.parse import quote, unquote
import moss


def inventory(vault):
    result = {}
    for p in sorted(vault.rglob('*')):
        if p.is_symlink() or (getattr(p.lstat(), 'st_file_attributes', 0) & 0x400):
            raise ValueError('Resolve symlinks/junctions before migration: ' + str(p))
        if p.is_file():
            result[p.relative_to(vault).as_posix()] = moss.digest(p.read_bytes())
    return result


def outside(path, vault):
    path = moss.absolute(path)
    if path == vault or vault in path.parents:
        raise ValueError('Keep migration artifacts outside the source vault')
    return path


def audit(vault, plan_path):
    vault = moss.absolute(vault)
    if not vault.is_dir() or vault == Path(vault.anchor) or vault == Path.home():
        raise ValueError('Choose an existing dedicated vault')
    plan_path = outside(plan_path, vault)
    if plan_path.exists():
        raise ValueError('Plan exists; retain it and choose a new path')
    hashes = inventory(vault)
    moves, duplicates = [], []
    by_hash = {}
    for rel, digest in hashes.items():
        if not rel.lower().endswith('.md') or rel.startswith('.'):
            continue
        by_hash.setdefault(digest, []).append(rel)
        text = (vault / rel).read_text(encoding='utf-8-sig')
        body = re.sub(r'\A---\r?\n.*?\r?\n---\r?\n', '', text, count=1, flags=re.S)
        # H1 is a suggestion, never an instruction to overwrite prose or metadata.
        heading = re.search(r'^# ([^\r\n]+)', body, re.M)
        old = PurePosixPath(rel)
        candidate = moss.title(heading[1] if heading else re.sub(r'[-_ ]+[a-fA-F0-9]{16,}$', '', old.stem))
        dest = old.with_name(candidate + '.md').as_posix()
        if dest != rel:
            moves.append({'from': rel, 'to': dest, 'reason': 'H1 or readable filename; review before prepare'})
    duplicates = [v for v in by_hash.values() if len(v) > 1]
    plan = {'format': 1, 'vault': str(vault), 'snapshot': hashes, 'moves': moves,
            'duplicate_candidates': duplicates, 'profile': {'domains': []}}
    moss.save(plan_path, plan)
    return {'plan': str(plan_path), 'files': len(hashes), 'proposed_renames': len(moves),
            'duplicate_groups': len(duplicates), 'source_changed': False}


def mapping_for(plan):
    snapshot = plan['snapshot']
    mapping = dict(zip(snapshot, snapshot))
    seen = set()
    for item in plan['moves']:
        src, dst = item['from'], item['to']
        if src in seen or src not in snapshot or not src.endswith('.md'):
            raise ValueError('Moves require unique existing Markdown sources: ' + src)
        seen.add(src)
        parts = PurePosixPath(dst).parts
        if not parts or dst.startswith('/') or '\\' in dst or any(p in ('.', '..') or ':' in p for p in parts):
            raise ValueError('Unsafe destination: ' + dst)
        if not dst.endswith('.md') or any(moss.title(p) != p for p in parts):
            raise ValueError('Use readable portable destination names: ' + dst)
        mapping[src] = dst
    targets = [v.casefold() for v in mapping.values()]
    if len(targets) != len(set(targets)):
        raise ValueError('Destination collision; choose distinct descriptive titles')
    return mapping


def resolve(target, source, files, relative=False):
    target = unquote(target).replace('\\', '/')
    if not target or target.startswith('#') or re.match(r'^[a-zA-Z][\w+.-]*:', target):
        return None
    norm = lambda s: os.path.normpath(s).replace('\\', '/')
    local = norm(str(PurePosixPath(source).parent / target))
    choices = [local, target.lstrip('/') ] if relative else [target.lstrip('/'), local]
    for name in choices:
        for candidate in (name, name + '.md'):
            if candidate in files:
                return candidate
    candidates = [p for p in files if PurePosixPath(p).name == target or
                  (p.endswith('.md') and PurePosixPath(p).stem == target)]
    if len(candidates) > 1:
        raise ValueError('Ambiguous link in ' + source + ': ' + target)
    return candidates[0] if candidates else None


def rewrite(text, source, mapping, issues):
    def target(value, relative=False):
        base, sep, fragment = value.partition('#')
        found = resolve(base, source, mapping, relative)
        if not found:
            if base and not re.match(r'^[a-zA-Z][\w+.-]*:', base):
                issues.append({'source': source, 'target': value})
            return value
        dest = mapping[found]
        if relative:
            dest = os.path.relpath(dest, str(PurePosixPath(mapping[source]).parent)).replace('\\', '/')
            dest = quote(dest, safe='/.-_~')
        elif dest.endswith('.md') and not base.endswith('.md'):
            dest = dest[:-3]
        return dest + (sep + fragment if sep else '')
    def wiki(m):
        name, bar, alias = m[1].partition('|')
        return '[[' + target(name) + (bar + alias if bar else '') + ']]'
    def markdown(m):
        raw = m[2]
        bracketed = raw.startswith('<')
        raw = raw[1:-1] if bracketed else raw
        result = target(raw, True)
        return m[1] + ('<' + result + '>' if bracketed else result) + m[3]
    # Code examples remain byte-for-byte text. Reference definitions are supported.
    chunks = re.split(r'(```[\s\S]*?```|~~~[\s\S]*?~~~|`[^`\n]*`)', text)
    for i in range(0, len(chunks), 2):
        part = re.sub(r'\[\[([^\]\n]+)\]\]', wiki, chunks[i])
        part = re.sub(r'(\]\()(<[^>\n]+>|[^\s()]+)(\s+[\"\'][^\n]*?[\"\']\)|\))', markdown, part)
        part = re.sub(r'(^\s*\[[^\]\n]+\]:\s*)(<[^>\n]+>|\S+)($|\s+[^\n]*)', markdown, part, flags=re.M)
        chunks[i] = part
    return ''.join(chunks)


def prepare(plan_path, output):
    plan = moss.read_json(Path(plan_path))
    vault = moss.absolute(plan['vault'])
    output = outside(output, vault)
    if output.exists():
        raise ValueError('Output exists; use a fresh directory')
    if inventory(vault) != plan['snapshot']:
        raise ValueError('Source changed since audit; create a fresh plan')
    mapping = mapping_for(plan)
    moss.validate_profile(plan['profile'])
    output.mkdir(parents=True)
    stage = output / 'vault'
    stage.mkdir()
    issues = []
    manual = []
    for src, dst in mapping.items():
        data = (vault / src).read_bytes()
        if src.endswith('.md'):
            text = data.decode('utf-8-sig')
            changed = rewrite(text, src, mapping, issues)
            if changed != text:
                data = (b'\xef\xbb\xbf' if data.startswith(b'\xef\xbb\xbf') else b'') + changed.encode('utf-8')
        elif src.endswith('.canvas'):
            canvas = json.loads(data)
            for node in canvas.get('nodes', []):
                if node.get('type') == 'file':
                    value = node['file']
                    if value not in mapping:
                        issues.append({'source': src, 'target': value})
                    else:
                        node['file'] = mapping[value]
                elif node.get('type') == 'text':
                    node['text'] = rewrite(node.get('text', ''), src, mapping, issues)
            data = (json.dumps(canvas, ensure_ascii=False, indent=2) + '\n').encode()
        dest = moss.inside(stage, dst)
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(data)
        if src.endswith(('.json', '.base', '.md')):
            # Surface path-bearing formats outside the supported link grammar.
            remaining = data.decode('utf-8-sig', errors='replace')
            for old, new in mapping.items():
                if old != new and (old in remaining or quote(old, safe='/') in remaining):
                    manual.append({'source': src, 'old_path': old,
                                   'reason': 'Remaining literal path; inspect query, metadata, example or plugin state'})
    # Fail rather than overwrite user home/rules/templates. Existing Moss migrations
    # are deliberately outside this adoption tool's scope.
    template = moss.SKILL / 'assets/vault'
    for p in template.rglob('*'):
        if not p.is_file():
            continue
        rel = p.relative_to(template)
        dest = stage / rel
        if dest.exists():
            if rel.parts[0] == '.obsidian':
                continue
            raise ValueError('Moss template conflicts with existing file: ' + str(rel) + '; relocate it in the plan')
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(p, dest)
    temp_config = output / 'preview-config.json'
    moss.save(temp_config, {'format': 1, 'vault': str(stage)})
    moss.configure(temp_config, plan['profile'])
    check = moss.doctor(temp_config)
    if not check['ok']:
        raise ValueError('Staged doctor failed: ' + str(check))
    # Baseline unresolved links are reported, not silently called repaired.
    report = {'format': 1, 'source': str(vault), 'source_snapshot': plan['snapshot'],
              'mapping': mapping, 'staged_snapshot': inventory(stage), 'doctor': check,
              'manual_reference_review': manual,
              'unresolved_baseline': issues,
              'limits': ['Semantic organization requires agent review of actual notes.',
                        'Title properties and headings are preserved; filenames are renamed.',
                        'Plugin queries, external incoming links and heading anchors require manual review.']}
    moss.save(output / 'report.json', report)
    return {'status': 'prepared', 'preview_vault': str(stage), 'report': str(output / 'report.json'),
            'source_changed': False, 'unresolved_links': len(issues)}


def activate(output, config, references_reviewed=False):
    output = moss.absolute(output)
    report = moss.read_json(output / 'report.json')
    if report.get('manual_reference_review') and not references_reviewed:
        raise ValueError('Inspect manual_reference_review, then pass --references-reviewed only after checking these references')
    source = moss.absolute(report['source'])
    outside(output, source)
    config = outside(config, source)
    if config.exists():
        raise ValueError('Use a new machine config for adoption')
    if inventory(source) != report['source_snapshot']:
        raise ValueError('Source changed; re-audit and prepare before activation')
    if inventory(output / 'vault') != report['staged_snapshot']:
        raise ValueError('Preview changed; prepare again instead of activating unverified files')
    # Stage on the same filesystem as source for directory renames. Original is
    # retained as a complete sibling backup, never recursively deleted.
    stage = Path(tempfile.mkdtemp(prefix='.moss-ready-', dir=source.parent))
    backup = stage.with_name(stage.name + '-original')
    if stage.parent.resolve() != source.parent.resolve() or backup.exists():
        raise ValueError('Invalid activation paths')
    shutil.copytree(output / 'vault', stage, dirs_exist_ok=True)
    if inventory(stage) != report['staged_snapshot'] or inventory(source) != report['source_snapshot']:
        raise ValueError('Concurrent change during activation; source untouched')
    source.rename(backup)
    try:
        stage.rename(source)
    except OSError:
        backup.rename(source)
        raise
    moss.save(output / 'activation.json', {'vault': str(source), 'backup': str(backup), 'config': str(config)})
    moss.save(config, {'format': 1, 'vault': str(source)})
    return {'status': 'activated', 'vault': str(source), 'backup': str(backup), 'doctor': moss.doctor(config)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    a = sub.add_parser('audit'); a.add_argument('--vault', required=True); a.add_argument('--plan', required=True)
    p = sub.add_parser('prepare'); p.add_argument('--plan', required=True); p.add_argument('--output', required=True)
    a = sub.add_parser('activate'); a.add_argument('--output', required=True); a.add_argument('--config', required=True)
    a.add_argument('--references-reviewed', action='store_true')
    args = parser.parse_args()
    try:
        result = (audit(args.vault, args.plan) if args.command == 'audit' else
                  prepare(args.plan, args.output) if args.command == 'prepare' else activate(args.output, args.config, args.references_reviewed))
        print(json.dumps(result, ensure_ascii=True))
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(json.dumps({'status': 'blocked', 'error': str(exc)})); return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
