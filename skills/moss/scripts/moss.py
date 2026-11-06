#!/usr/bin/env python3
"""Moss: local project memory. Python 3.10+, standard library only."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import sys
import tempfile
from contextlib import contextmanager
from datetime import date, datetime, timezone

VERSION = '0.3.0'
SKILL = Path(__file__).resolve().parents[1]
PALETTE = ('#4879C4', '#35A38B', '#DE9745', '#8672BD', '#CF7895', '#619846', '#A98A61', '#7D8897')
FIELDS = ('facts', 'decisions', 'failures', 'fixes', 'verification', 'unverified', 'sources', 'reuse_conditions', 'next_steps')
BEGIN, END = '<!-- MOSS:BEGIN -->', '<!-- MOSS:END -->'


def digest(data):
    return hashlib.sha256(data).hexdigest()


def read_json(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix='.moss-', dir=path.parent)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8', newline='\n') as f:
            f.write(text)
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def save(path, data):
    write(path, json.dumps(data, ensure_ascii=False, indent=2) + '\n')


def inside(root, relative):
    root = root.resolve()
    path = (root / relative).resolve()
    if path == root or root not in path.parents:
        raise ValueError('Path must stay inside its owning directory')
    return path


def absolute(value):
    path = Path(value).expanduser()
    if not path.is_absolute():
        raise ValueError('Use an absolute path')
    return path.resolve()


def title(value):
    value = re.sub(r'[<>:"/\\|?*\[\]#\x00-\x1f]', ' ', value)
    value = re.sub(r'\s+', ' ', value).strip(' .')[:100].rstrip()
    if not value:
        raise ValueError('A readable title is required')
    if re.fullmatch(r'(?i)(CON|PRN|AUX|NUL|COM[0-9]|LPT[0-9])(?:\..*)?', value):
        value = 'Note ' + value
    return value


def key(value):
    if not re.fullmatch(r'[a-z0-9][a-z0-9-]{0,63}', value):
        raise ValueError('Key must be lowercase letters, digits and hyphens (max 64)')
    return value


def note(meta, body):
    # A JSON object is valid YAML and round-trips without third-party packages.
    return '---\n' + json.dumps(meta, ensure_ascii=False, indent=2) + '\n---\n\n' + body.strip() + '\n'


def parse_note(path):
    text = path.read_text(encoding='utf-8-sig')
    match = re.match(r'\A---\n(.*?)\n---\n(.*)\Z', text, re.S)
    if not match:
        raise ValueError('Missing Moss frontmatter: ' + path.name)
    try:
        return json.loads(match[1]), match[2]
    except json.JSONDecodeError as exc:
        raise ValueError('Moss-managed record metadata must remain a JSON object: ' + path.name) from exc


@contextmanager
def lock(path):
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        path.mkdir()
    except FileExistsError as exc:
        raise ValueError('Another writer or interrupted write holds ' + str(path) + '; inspect before removing the lock') from exc
    try:
        yield
    finally:
        path.rmdir()


def load(config):
    if not config.exists():
        raise ValueError('Moss is not configured. Run setup first.')
    settings = read_json(config)
    vault = absolute(settings['vault'])
    if not vault.is_dir() or read_json(vault / 'System/moss.json') != {'owner': 'moss', 'format': 1}:
        raise ValueError('Not a Moss-managed vault')
    registry = read_json(vault / 'System/projects.json')
    if registry.get('format') != 1:
        raise ValueError('Unsupported project registry')
    return vault, registry, settings


def instruction_text(config):
    return f'''{BEGIN}
## Moss project memory
For substantive project starts, resumptions and meaningful completions, use $moss
at `{SKILL.as_posix()}/SKILL.md`. For this installation always pass
`--config "{config.resolve().as_posix()}"` before the helper subcommand.
Identify the actual project root; read its hub
and relevant dated lessons before working. At a milestone or stop, record useful
decisions, failures, evidence, actual checks and reuse conditions in the configured
local Obsidian vault. Skip casual chat and trivial edits. Respect read-only/no-memory
requests, project instructions and filesystem permissions. Keep projects distinct;
do not promote drafts to verified truth or copy general principles into every log.
Do not change other AI configurations or publish private vault content.
{END}'''


def instructions(path, config):
    old = path.read_text(encoding='utf-8') if path.exists() else ''
    if old.count(BEGIN) != old.count(END) or old.count(BEGIN) > 1:
        raise ValueError('Malformed or duplicate Moss instruction block')
    if BEGIN in old:
        start, end = old.index(BEGIN), old.index(END) + len(END)
        if end < start:
            raise ValueError('Malformed Moss instruction block')
        new = old[:start] + instruction_text(config) + old[end:]
    else:
        # Avoid silently competing with an already configured memory workflow.
        if '$obsidian-project-memory' in old or re.search(r'<!--\s*BEGIN[^>]*OBSIDIAN PROJECT MEMORY\s*-->', old, re.I):
            raise ValueError('An existing Obsidian memory instruction is present; reconcile it before enabling Moss')
        new = old.rstrip() + ('\n\n' if old.strip() else '') + instruction_text(config) + '\n'
    return old, new


def setup(config, vault, agents=None, profile=None):
    if profile is not None:
        validate_profile(profile)  # reject bad input before creating any files
    vault = absolute(vault)
    config = absolute(config)
    if vault == Path(vault.anchor) or vault == Path.home().resolve():
        raise ValueError('Choose a dedicated vault directory')
    if vault == config or vault in config.parents:
        raise ValueError('Keep the machine configuration outside the vault')
    existing = read_json(config) if config.exists() else None
    if existing and absolute(existing['vault']) != vault:
        raise ValueError('This config already points to another vault; use a separate --config')
    managed = (vault / 'System/moss.json').exists()
    if managed and read_json(vault / 'System/moss.json') != {'owner': 'moss', 'format': 1}:
        raise ValueError('Vault marker belongs to another workflow')
    if vault.exists() and not managed and any(vault.iterdir()):
        raise ValueError('Use a new or empty vault; setup never merges an existing vault')
    agents = absolute(agents) if agents else None
    if agents and (agents == config or agents == vault or vault in agents.parents):
        raise ValueError('Instructions must be a separate external AGENTS.md file')
    if agents and agents.name != 'AGENTS.md':
        raise ValueError('Instruction target must be named AGENTS.md')
    old, new = instructions(agents, config) if agents else ('', '')
    with lock(config.with_suffix('.setup-lock')):
        if not managed:
            vault.parent.mkdir(parents=True, exist_ok=True)
            stage = Path(tempfile.mkdtemp(prefix='.moss-vault-', dir=vault.parent))
            try:
                shutil.copytree(SKILL / 'assets/vault', stage, dirs_exist_ok=True)
                if vault.exists():
                    vault.rmdir()  # only an empty directory; a concurrent addition causes failure
                stage.rename(vault)
            finally:
                if stage.exists():
                    shutil.rmtree(stage)  # generated temporary directory only
        settings = existing or {'format': 1, 'vault': str(vault)}
        if agents:
            if old != new:
                if agents.exists():
                    backup = config.parent / 'backups' / ('AGENTS-' + digest(old.encode())[:16] + '.md')
                    if not backup.exists():
                        write(backup, old)
                write(agents, new)
            settings['instructions'] = str(agents)
        save(config, settings)
    customization = configure(config, profile) if profile is not None else None
    return {'status': 'ready', 'vault': str(vault), 'instructions': settings.get('instructions'), 'customization': customization, 'doctor': doctor(config)}


def domain_id(value):
    if not isinstance(value, str) or not re.fullmatch(r'[A-Za-z][A-Za-z0-9-]{0,47}', value):
        raise ValueError('Domain id must start with a letter and use letters, digits or hyphens (max 48)')
    if title(value) != value or value.casefold() == 'shared':
        raise ValueError('Reserved domain id: ' + value)
    if value.casefold() == 'unsorted' and value != 'Unsorted':
        raise ValueError('Use the canonical fallback id Unsorted')
    return value


def validate_profile(profile):
    if not isinstance(profile, dict) or set(profile) != {'domains'} or not isinstance(profile['domains'], list):
        raise ValueError('Profile must contain a domains array')
    seen = set()
    for d in profile['domains']:
        if not isinstance(d, dict) or set(d) != {'id', 'label', 'color'}:
            raise ValueError('Each domain needs id, label and color')
        domain_id(d['id'])
        if d['id'].casefold() in seen:
            raise ValueError('Duplicate domain id (case-insensitive)')
        seen.add(d['id'].casefold())
        if not isinstance(d['label'], str) or not d['label'].strip() or len(d['label']) > 80 or re.search(r'[\r\n\[\]|<>\x00-\x1f]', d['label']):
            raise ValueError('Use a short, single-line domain label without markup delimiters')
        if not isinstance(d['color'], str) or not re.fullmatch(r'#[0-9a-fA-F]{6}', d['color']):
            raise ValueError('Use a six-digit hex color such as #4879C4')


def domain_state(vault, reg):
    path = vault / 'System/domains.json'
    if path.exists():
        state = read_json(path)
        if state.get('format') != 1 or not isinstance(state.get('generated'), dict):
            raise ValueError('Unsupported domain registry')
        validate_profile({'domains': state['domains']})
        return state
    # v0.1 compatibility: infer the existing taxonomy, never import the author's list.
    ids = {p['domain'] for p in reg['projects'].values()}
    for area in (vault / 'Areas').glob('*.md'):
        meta, _ = parse_note(area)
        if meta.get('domain'):
            ids.add(meta['domain'])
    graph = read_json(vault / '.obsidian/graph.json')
    colors = {g['query']: g.get('color', {}).get('rgb') for g in graph.get('colorGroups', [])}
    domains = []
    for i, value in enumerate(sorted(ids)):
        domain_id(value)
        rgb = colors.get('[domain:' + value + ']')
        color = '#%06X' % rgb if isinstance(rgb, int) and 0 <= rgb <= 0xFFFFFF else PALETTE[i % len(PALETTE)]
        domains.append({'id': value, 'label': value, 'color': color})
    return {'format': 1, 'domains': domains, 'generated': {}}


def domains(config):
    vault, reg, _ = load(config)
    return {'domains': domain_state(vault, reg)['domains'], 'writes': False}


def configure(config, profile):
    """Merge labels/colors/categories, without moving projects or editing record bodies."""
    validate_profile(profile)
    vault, _, _ = load(config)
    with lock(vault / 'System/.write-lock'):
        vault, reg, _ = load(config)
        state = domain_state(vault, reg)
        pending = state.get('pending')
        if pending and pending['profile'] != profile:
            raise ValueError('Interrupted category update; retry its exact profile first')
        merged = {d['id']: dict(d) for d in state['domains']}
        for d in profile['domains']:
            if any(k.casefold() == d['id'].casefold() and k != d['id'] for k in merged):
                raise ValueError('Domain id differs only in case from an existing id')
            merged[d['id']] = dict(d)
        desired = list(merged.values())
        planned = {}
        rows, nodes = [], []
        for i, d in enumerate(desired):
            ident, label = d['id'], d['label']
            area = f'Areas/{ident}.md'
            view = f'System/Views/Area-{ident}.base'
            # Existing area prose and views stay user-owned, including v0.1 material.
            if not (vault / view).exists() or view in state['generated']:
                planned[view] = json.dumps({'filters': {'and': ['type == "project"', 'domain == ' + json.dumps(ident)]}, 'views': [{'type': 'table', 'name': 'Projects', 'order': ['file.name']}]}, indent=2) + '\n'
            if not (vault / area).exists() or area in state['generated']:
                planned[area] = note({'type': 'navigation', 'domain': ident, 'wiki_layer': 'navigation', 'graph_role': 'navigation'}, '# ' + label + '\n\n![[' + view + ']]')
            rows.append('| [[' + area[:-3] + '|' + label + ']] | `' + ident + '` | `' + d['color'] + '` |')
            nodes.append({'id': 'domain-' + ident, 'type': 'file', 'file': area, 'x': (i % 3) * 340, 'y': (i // 3) * 280, 'width': 300, 'height': 220, 'color': d['color']})
        body = '# Your areas\n\nLabels and colors come from `System/domains.json`. Add only categories that help you find your work.\n\n'
        body += '| Area | Stable ID | Color |\n|---|---|---|\n' + '\n'.join(rows) if rows else 'No categories yet. Start with a project; use Unsorted until a useful distinction emerges.'
        planned['System/Areas.md'] = note({'type': 'navigation', 'wiki_layer': 'navigation', 'graph_role': 'navigation'}, body)
        if not nodes:
            nodes = [{'id': 'empty', 'type': 'text', 'text': 'No categories yet. Add your own when useful.', 'x': 0, 'y': 0, 'width': 480, 'height': 180}]
        planned['System/Domain Map.canvas'] = json.dumps({'nodes': nodes, 'edges': []}, ensure_ascii=False, indent=2) + '\n'
        generated = dict(state['generated'])
        # Only generated navigation is replaceable, and only while unedited.
        for rel in planned:
            path = inside(vault, rel)
            if path.exists() and path.read_text('utf-8') != planned[rel]:
                if digest(path.read_bytes()) not in {generated.get(rel), (pending or {}).get('before', {}).get(rel)}:
                    raise ValueError('User-edited navigation preserved: ' + rel + '; reconcile it before configuring')
        graph_path = vault / '.obsidian/graph.json'
        graph = read_json(graph_path)
        replacements = {'[domain:' + d['id'] + ']': {'query': '[domain:' + d['id'] + ']', 'color': {'a': 1, 'rgb': int(d['color'][1:], 16)}} for d in desired}
        groups = []
        for group in graph.get('colorGroups', []):
            query = group.get('query')
            if query in replacements:
                groups.append(replacements.pop(query))
            elif query not in {'[domain:' + d['id'] + ']' for d in desired}:
                groups.append(group)
        groups.extend(replacements.values())
        graph['colorGroups'] = groups
        planned['.obsidian/graph.json'] = json.dumps(graph, ensure_ascii=False, indent=2) + '\n'
        home = (vault / 'Home.md').read_text('utf-8')
        if '[[System/Areas' not in home:
            planned['Home.md'] = home.rstrip() + '\n\n## Your areas\n\n[[System/Areas|Browse your categories]] · [[System/Domain Map.canvas|Your category map]]\n'
        before = dict(generated)
        for rel in planned:
            if rel in ('Home.md', '.obsidian/graph.json'):
                continue
            generated[rel] = digest(planned[rel].encode('utf-8'))
        old = vault / 'System/domains.json'
        if old.exists():
            backup = vault / 'System/Backups' / ('domains-' + digest(old.read_bytes())[:16] + '.json')
            if not backup.exists():
                write(backup, old.read_text('utf-8'))
        save(old, {'format': 1, 'domains': desired, 'generated': generated,
                   'pending': {'profile': profile, 'before': (pending or {}).get('before', before)}})
        for rel, content in planned.items():
            path = inside(vault, rel)
            if not path.exists() or path.read_text('utf-8') != content:
                write(path, content)
        save(old, {'format': 1, 'domains': desired, 'generated': generated})
    return {'status': 'configured', 'domains': desired, 'preserved': 'Existing projects, records, area prose, Canvas and unrelated graph settings'}


def project_root(value):
    root = absolute(value)
    if not root.is_dir():
        raise ValueError('Project root must be an existing directory')
    return root


def select(registry, root, chosen=None):
    matches = [k for k, p in registry['projects'].items() if absolute(p['root']) == root]
    if chosen:
        key(chosen)
        if chosen not in matches:
            raise ValueError('Project key is not registered for this exact root')
        return chosen
    if len(matches) > 1:
        raise ValueError('Multiple projects share this root; select --key: ' + ', '.join(matches))
    if not matches:
        raise ValueError('Register this exact project root first')
    return matches[0]


def base(chosen):
    return {'filters': {'and': ['type == "task-record"', 'project_key == ' + json.dumps(chosen)]},
            'properties': {'note.evidence_as_of': {'displayName': 'Evidence date'}, 'note.record_status': {'displayName': 'Review'}, 'note.revision': {'displayName': 'Revision'}},
            'views': [{'type': 'table', 'name': 'Latest per task', 'filters': 'record_current == true', 'order': ['file.name', 'note.evidence_as_of', 'note.record_status'], 'sort': [{'property': 'note.evidence_as_of', 'direction': 'DESC'}]},
                      {'type': 'table', 'name': 'All revisions', 'order': ['file.name', 'note.evidence_as_of', 'note.revision']} ]}


def support(vault, chosen, p):
    view = inside(vault, 'System/Views/' + chosen + '.base')
    if not view.exists():
        save(view, base(chosen))
    hub = inside(vault, p['hub'])
    if not hub.exists():
        write(hub, note({'type': 'project', 'domain': p['domain'], 'project_key': chosen, 'wiki_layer': 'project'},
                        '# ' + p['title'] + '\n\nRead relevant records and their sources before resuming. The last draft is not verified current truth.\n\n![[System/Views/' + chosen + '.base]]\n\n## Shared knowledge\nLink principles only when you can explain the relationship.'))


def register(config, root, chosen, name, domain='Unsorted'):
    root, chosen, name = project_root(root), key(chosen), title(name)
    domain_id(domain)
    vault, reg, _ = load(config)
    state = domain_state(vault, reg)
    if state.get('pending'):
        raise ValueError('Retry the interrupted configure profile before registering projects')
    known = {d['id'] for d in state['domains']}
    if domain not in known:
        if domain != 'Unsorted':
            raise ValueError('Domain is not configured; use configure --profile before registering it')
        configure(config, {'domains': [{'id': 'Unsorted', 'label': 'Unsorted', 'color': '#7D8897'}]})
    with lock(vault / 'System/.write-lock'):
        vault, reg, _ = load(config)
        p = {'title': name, 'domain': domain, 'root': str(root), 'hub': f'Projects/{domain}/{name}.md', 'folder': f'Records/{domain}/{name}'}
        if chosen in reg['projects']:
            if reg['projects'][chosen] != p:
                raise ValueError('Project key already registered with different settings')
        else:
            if any(x['hub'].casefold() == p['hub'].casefold() for x in reg['projects'].values()):
                raise ValueError('Title already used in this domain; choose a meaningful distinction')
            reg['projects'][chosen] = p
            save(vault / 'System/projects.json', reg)
        support(vault, chosen, p)
    return {'status': 'registered', 'key': chosen, 'hub': str(vault / p['hub'])}


def records(vault, p):
    folder = inside(vault, p['folder'])
    return [(f, *parse_note(f)) for f in sorted(folder.glob('*.md'))] if folder.exists() else []


def start(config, root, chosen=None):
    root = project_root(root)
    vault, reg, _ = load(config)
    matches = [k for k, p in reg['projects'].items() if absolute(p['root']) == root]
    if not chosen and len(matches) != 1:
        return {'status': 'selection_required' if matches else 'registration_required', 'candidates': matches, 'writes': False}
    chosen = select(reg, root, chosen)
    p = reg['projects'][chosen]
    recent = sorted(((f, m) for f, m, _ in records(vault, p) if m.get('record_current')), key=lambda x: x[1]['created_at'], reverse=True)[:8]
    return {'key': chosen, 'hub': str(vault / p['hub']), 'recent_records': [str(f) for f, _ in recent], 'writes': False, 'note': 'Read relevant source evidence; recent does not mean verified.'}


def validate(data):
    required = {'task_id', 'title', 'goal', 'outcome', 'evidence_as_of', *FIELDS}
    if not isinstance(data, dict) or set(data) != required:
        raise ValueError('Input fields must match references/record.example.json')
    key(data['task_id'])
    for field in ('title', 'goal', 'evidence_as_of'):
        if not isinstance(data[field], str) or not data[field].strip():
            raise ValueError('Missing ' + field)
    if '\n' in data['title'] or len(data['title']) > 180:
        raise ValueError('Use a short, single-line title')
    date.fromisoformat(data['evidence_as_of'])
    if data['outcome'] not in ('completed', 'partial', 'blocked', 'cancelled'):
        raise ValueError('Invalid outcome')
    for field in FIELDS:
        if not isinstance(data[field], list) or any(not isinstance(v, str) or not v.strip() for v in data[field]):
            raise ValueError('Expected a list of nonempty strings: ' + field)
    if not all(data[f] for f in ('facts', 'sources', 'reuse_conditions')):
        raise ValueError('Facts, sources and reuse conditions are required')
    if not data['verification'] and not data['unverified']:
        raise ValueError('State actual verification or its limits')
    if len(json.dumps(data)) > 40000:
        raise ValueError('Link large evidence rather than copying it')


def record(config, root, data, chosen=None):
    validate(data)
    root = project_root(root)
    vault, _, _ = load(config)
    with lock(vault / 'System/.write-lock'):
        vault, reg, _ = load(config)
        chosen = select(reg, root, chosen)
        p = reg['projects'][chosen]
        route = str(root) + '|' + data['task_id']
        if route in reg['routes'] and reg['routes'][route] != chosen:
            raise ValueError('This task already belongs to a different project')
        reg['routes'][route] = chosen
        save(vault / 'System/projects.json', reg)
        support(vault, chosen, p)
        prior = sorted((r for r in records(vault, p) if r[1]['task_id'] == data['task_id']), key=lambda r: r[1]['revision'])
        content_hash = digest(json.dumps(data, sort_keys=True, ensure_ascii=False).encode())
        same = next((f for f, m, _ in prior if m['content_sha256'] == content_hash), None)
        if same:
            # Repair flags after a successful draft write followed by an interrupted flag update.
            for i, (f, m, body) in enumerate(prior):
                current = i == len(prior) - 1
                if m['record_current'] != current:
                    m['record_current'] = current
                    write(f, note(m, body))
            return {'status': 'unchanged', 'note': str(same)}
        revision = max((m['revision'] for _, m, _ in prior), default=0) + 1
        stem = title(data['title']) + ' — ' + data['evidence_as_of'] + (f' (revision {revision})' if prior else '')
        dest = inside(vault, p['folder'] + '/' + stem + '.md')
        n = 2
        while dest.exists():
            dest = inside(vault, p['folder'] + '/' + stem + f' ({n}).md')
            n += 1
        meta = {'type': 'task-record', 'domain': p['domain'], 'project_key': chosen, 'wiki_layer': 'log', 'record_status': 'draft', 'reviewed': None, 'task_id': data['task_id'], 'content_sha256': content_hash, 'revision': revision, 'record_current': True, 'evidence_as_of': data['evidence_as_of'], 'created_at': datetime.now(timezone.utc).isoformat(), 'outcome': data['outcome']}
        body = '# ' + data['title'] + '\n\n> Working draft. Check evidence dates and sources.\n\n## Goal\n' + data['goal'] + '\n'
        if prior:
            body += '\nPrevious revision: [[' + prior[-1][0].relative_to(vault).with_suffix('').as_posix() + ']]\n'
        for field in FIELDS:
            body += '\n## ' + field.replace('_', ' ').capitalize() + '\n' + ('\n'.join('- ' + v.replace('\n', '\n  ') for v in data[field]) or '- None recorded') + '\n'
        body += '\nProject: [[' + Path(p['hub']).with_suffix('').as_posix() + '|' + p['title'] + ']]\n'
        write(dest, note(meta, body))
        for f, m, oldbody in prior:
            if m['record_current']:
                m['record_current'] = False
                write(f, note(m, oldbody))
    return {'status': 'created', 'note': str(dest), 'revision': revision}


def doctor(config):
    vault, reg, settings = load(config)
    errors, warnings = [], []
    state = domain_state(vault, reg)
    known = {d['id'] for d in state['domains']}
    if state.get('pending'):
        errors.append('Interrupted category update; retry the exact configure profile')
    if not (vault / 'System/domains.json').exists():
        warnings.append('Legacy taxonomy detected; configure --profile imports it without moving records')
    else:
        graph = read_json(vault / '.obsidian/graph.json')
        colors = {g.get('query'): g.get('color', {}).get('rgb') for g in graph.get('colorGroups', [])}
        for d in state['domains']:
            if not (vault / ('Areas/' + d['id'] + '.md')).is_file():
                errors.append('Missing domain area: ' + d['id'])
            if not (vault / ('System/Views/Area-' + d['id'] + '.base')).is_file():
                errors.append('Missing domain view: ' + d['id'])
            if colors.get('[domain:' + d['id'] + ']') != int(d['color'][1:], 16):
                warnings.append('Graph color differs from domain registry: ' + d['id'])
    for rel in ('Home.md', 'Knowledge Map.canvas', 'System/Rules.md', 'System/Views/Projects.base', '.obsidian/graph.json'):
        if not inside(vault, rel).is_file():
            errors.append('Missing ' + rel)
    count = 0
    for chosen, p in reg['projects'].items():
        key(chosen)
        if p['domain'] not in known:
            errors.append('Unknown project domain: ' + chosen)
        if not inside(vault, p['hub']).exists() or not inside(vault, 'System/Views/' + chosen + '.base').exists():
            errors.append('Missing hub or view: ' + chosen)
        if not Path(p['root']).is_dir():
            warnings.append('Source root unavailable: ' + chosen)
        tasks = {}
        for f, m, _ in records(vault, p):
            count += 1
            if m.get('project_key') != chosen:
                errors.append('Wrong project: ' + f.name)
            tasks.setdefault(m['task_id'], []).append(m)
        for task, revisions in tasks.items():
            if sum(m.get('record_current') is True for m in revisions) != 1:
                errors.append('Expected one current revision: ' + chosen + '/' + task)
    # Check native Canvas targets and the generated JSON-subset Bases files.
    for path in vault.rglob('*.base'):
        read_json(path)
    for path in vault.rglob('*.canvas'):
        canvas = read_json(path)
        ids = {n['id'] for n in canvas['nodes']}
        if len(ids) != len(canvas['nodes']):
            errors.append('Duplicate canvas node: ' + path.name)
        for n in canvas['nodes']:
            if n.get('type') == 'file' and not inside(vault, n['file']).is_file():
                errors.append('Missing canvas target: ' + n['file'])
        for e in canvas['edges']:
            if e['fromNode'] not in ids or e['toNode'] not in ids:
                errors.append('Missing canvas edge endpoint')
    agents = settings.get('instructions')
    if agents:
        content = Path(agents).read_text(encoding='utf-8') if Path(agents).exists() else ''
        if instruction_text(config) not in content:
            errors.append('Moss instruction block missing or stale; rerun setup with --instructions')
    else:
        warnings.append('Standing instructions not enabled; invoke $moss explicitly')
    return {'ok': not errors, 'projects': len(reg['projects']), 'domains': len(known), 'records': count, 'errors': errors, 'warnings': warnings, 'scope': 'Structure, routing and revision flags; not factual accuracy or every note link.'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--version', action='version', version=VERSION)
    parser.add_argument('--config', type=Path, default=Path(os.environ.get('MOSS_CONFIG', str(Path.home() / '.moss/config.json'))))
    sub = parser.add_subparsers(dest='command', required=True)
    init = sub.add_parser('setup')
    init.add_argument('--vault', required=True)
    init.add_argument('--instructions', help='Explicit AGENTS.md target; omitted means no instruction edits')
    init.add_argument('--profile', type=Path)
    sub.add_parser('doctor')
    sub.add_parser('domains')
    customize = sub.add_parser('configure')
    customize.add_argument('--profile', type=Path, required=True)
    for mode in ('start', 'register', 'record'):
        cmd = sub.add_parser(mode)
        cmd.add_argument('--project', required=True)
        cmd.add_argument('--key', required=mode == 'register')
        if mode == 'register':
            cmd.add_argument('--title', required=True)
            cmd.add_argument('--domain', default='Unsorted')
        if mode == 'record':
            cmd.add_argument('--input', type=Path, required=True)
    args = parser.parse_args()
    try:
        if args.command == 'setup':
            result = setup(args.config, args.vault, args.instructions, read_json(args.profile) if args.profile else None)
        elif args.command == 'doctor':
            result = doctor(args.config)
        elif args.command == 'domains':
            result = domains(args.config)
        elif args.command == 'configure':
            result = configure(args.config, read_json(args.profile))
        elif args.command == 'start':
            result = start(args.config, args.project, args.key)
        elif args.command == 'register':
            result = register(args.config, args.project, args.key, args.title, args.domain)
        else:
            result = record(args.config, args.project, read_json(args.input), args.key)
        print(json.dumps(result, ensure_ascii=True))
        return 1 if result.get('ok') is False or result.get('doctor', {}).get('ok') is False else 0
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(json.dumps({'status': 'blocked', 'error': str(exc)}, ensure_ascii=True))
        return 1


if __name__ == '__main__':
    sys.exit(main())
