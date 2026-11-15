#!/usr/bin/env python3
"""Build and audit a deterministic, source-only candidate; never publish it."""
import argparse
import hashlib
import json
import re
import subprocess
import urllib.parse
from pathlib import Path

ROOT_FILES = {'.gitignore', '.gitattributes', 'README.md', 'LICENSE', 'NOTICE.md', 'AGENTS.md', 'CONTRIBUTING.md', 'omrender', 'omfit', 'build-comparator.sh'}
SCRIPTS = {'build.sh', 'build-comparator.sh', 'omrender', 'doctor.py', 'doctor', 'install.sh', 'test-native-rng.py', 'test-profile-readback.py', 'test-profile-transport.py', 'release-audit.py'}
HELD_RECIPES = {'kodachrome25.xmp', 'kodachrome64.xmp', 'velvia50.xmp'}
PRIVATE = re.compile(rb'/Users/(?!YOUR_USER\b|example\b)[A-Za-z0-9_.-]+/|' + rb'/Volumes/' + rb'[^\s"\']+')
SERIAL = re.compile(rb'\bBHNA[0-9]{5}\b')
SECRET = re.compile(rb'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----|\b(?:AKIA|ASIA)[A-Z0-9]{16}\b|\bghp_[A-Za-z0-9]{36}\b')
BINARY = (b'\xcf\xfa\xed\xfe', b'\xfe\xed\xfa\xcf', b'PK\x03\x04', b'%PDF', b'\x7fELF')

def allowed(name):
    p = Path(name)
    if name in ROOT_FILES: return True
    if name.startswith(('optimizer/experiments/', 'optimizer/.venv/', 'docs/open-source-review/')): return False
    if name.startswith('optimizer/src/omfit/'):
        return p.suffix in ('.py', '.oes') and p.name != 'relative_benchmark.py'
    if name.startswith('optimizer/tests/'): return p.suffix == '.py'
    if name in ('optimizer/pyproject.toml', 'optimizer/uv.lock', 'optimizer/README.md', 'optimizer/LICENSE', 'optimizer/NOTICE.md'): return True
    if name.startswith(('examples/', 'settings/')): return p.suffix in ('.json', '.oes', '.md')
    if name.startswith('optimizer/examples/'): return p.suffix in ('.json', '.md')
    if name.startswith('optimizer/recipes/'):
        return p.suffix in ('.json', '.oes', '.xmp', '.md') and p.name not in HELD_RECIPES
    if name.startswith('scripts/'): return p.name in SCRIPTS
    if name.startswith('tests/'): return p.suffix in ('.py', '.mm', '.json', '.oes')
    if name.startswith('docs/'):
        return name in ('docs/CLI-HELP.md', 'docs/install.md', 'docs/quickstart.md', 'docs/compatibility.md', 'docs/release-readiness.md') or name.startswith(('docs/users/', 'docs/developers/', 'docs/reference/'))
    if name.startswith('legal/'):
        return p.suffix in ('.md', '.txt')
    if name.startswith('.github/workflows/'): return p.suffix in ('.yml', '.yaml')
    return False

def git(root, *args):
    return subprocess.check_output(['git', '-C', str(root), *args])

def selection(root, ref):
    names = git(root, 'ls-tree', '-r', '--name-only', ref).decode().splitlines()
    selected = {n for n in names if allowed(n)}
    pending = ['src/omrender.mm', 'src/compare_pixels.mm', 'src/native_rng_fault_test.mm']
    while pending:
        name = pending.pop()
        if name in selected: continue
        if name not in names: raise ValueError('Required production source is absent from candidate commit: ' + name)
        selected.add(name)
        source = git(root, 'show', ref + ':' + name).decode()
        pending.extend(str(Path(name).parent / inc) for inc in re.findall(r'^\s*#include\s+"([^"]+)"', source, re.M))
    return sorted(selected), sorted(set(names) - selected)

def audit(tree):
    findings = []
    for p in sorted(tree.rglob('*')):
        if p.is_symlink(): findings.append({'path':str(p.relative_to(tree)), 'issue':'symlink forbidden in candidate'}); continue
        if not p.is_file(): continue
        rel = str(p.relative_to(tree)); data = p.read_bytes()
        if rel == 'release-manifest.json': continue
        if any(x in p.parts for x in ('.git', '.venv', '__pycache__', '.ruff_cache')): findings.append({'path':rel,'issue':'generated/private directory'})
        if p.suffix.lower() in ('.dylib', '.o', '.orf', '.jpg', '.tif', '.tiff', '.dcp', '.icc', '.icm', '.set') or data.startswith(BINARY): findings.append({'path':rel,'issue':'binary/media/vendor/backup asset requires separate review'})
        # Audit program contains the detection patterns as source, not an identity.
        for kind, pattern in [('personal_path', PRIVATE), ('camera_identity', SERIAL), ('credential_pattern', SECRET)]:
            if pattern.search(data): findings.append({'path':rel,'issue':kind})
        if p.name in HELD_RECIPES: findings.append({'path':rel,'issue':'community recipe rights hold'})
        if p.suffix == '.md':
            for link in re.findall(r'\[[^\]]*\]\(([^)]+)\)', data.decode('utf-8', errors='replace')):
                if '://' in link or link.startswith(('mailto:', '#')): continue
                local = urllib.parse.unquote(link.split('#')[0])
                target = (p.parent / local).resolve()
                if not target.is_relative_to(tree.resolve()) or not target.exists():
                    findings.append({'path':rel,'issue':'missing or external local documentation target'})

    return findings

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-root', type=Path, default=Path(__file__).resolve().parent.parent)
    parser.add_argument('--ref', default='HEAD', help='Committed source revision, never the dirty worktree')
    parser.add_argument('--output', type=Path, help='New candidate directory; refuses existing paths')
    parser.add_argument('--tree', type=Path, help='Audit an already exported candidate')
    args = parser.parse_args()
    try:
        if args.tree:
            findings = audit(args.tree.resolve()); result = {'status':'failed' if findings else 'candidate_audit_passed', 'findings':findings, 'publication_cleared':False}
        else:
            selected, excluded = selection(args.source_root, args.ref)
            result = {'source_commit':git(args.source_root,'rev-parse',args.ref).decode().strip(), 'selected_files':selected, 'excluded_files':excluded, 'publication_cleared':False, 'legal_and_fresh_mac_gates':'See legal/RELEASE-BLOCKERS.md and docs/release-readiness.md'}
            if args.output:
                args.output.mkdir(parents=True, exist_ok=False)
                manifest = []
                for name in selected:
                    data = git(args.source_root,'show',args.ref+':'+name)
                    destination=args.output/name; destination.parent.mkdir(parents=True,exist_ok=True);destination.write_bytes(data)
                    mode=git(args.source_root,'ls-tree',args.ref,'--',name).decode().split()[0]
                    if mode=='120000': raise ValueError('Git symlink forbidden in candidate: '+name)
                    if mode=='100755': destination.chmod(0o755)
                    manifest.append({'path':name,'sha256':hashlib.sha256(data).hexdigest()})
                result['files']=manifest; result['findings']=audit(args.output)
                result['status']='failed' if result['findings'] else 'candidate_audit_passed'
                (args.output/'release-manifest.json').write_text(json.dumps(result,indent=2)+'\n')
            else: result['status']='selection_only'
        print(json.dumps(result,indent=2)); return 1 if result.get('status')=='failed' else 0
    except (ValueError, OSError, subprocess.CalledProcessError) as exc:
        print(json.dumps({'status':'error','error':str(exc),'publication_cleared':False}));return 2

if __name__=='__main__': raise SystemExit(main())
