#!/usr/bin/env python3
"""Read-only prerequisite diagnostics. Never loads vendor code or opens USB."""
import argparse
import ctypes.util
import json
import platform
import plistlib
import shutil
import subprocess
import sys
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--optimizer', action='store_true', help='require optimizer prerequisites')
    parser.add_argument('--adobe', action='store_true', help='require optional Adobe prerequisites')
    parser.add_argument('--json', action='store_true', help='machine-readable output')
    args = parser.parse_args()
    root = Path(__file__).resolve().parent.parent
    checks = []

    def check(name, available, detail, remedy, required=True):
        checks.append(dict(name=name, available=bool(available), required=required,
                           detail=str(detail), remedy=remedy if not available else ''))

    check('platform', sys.platform == 'darwin' and platform.machine() == 'arm64',
          f'{platform.system()} {platform.mac_ver()[0]} {platform.machine()}',
          'Native rendering requires an Apple Silicon Mac; run outside Rosetta.')
    check('python', sys.version_info >= (3, 9), platform.python_version(), 'Install Python 3.9 or later for omrender.')
    compiler = shutil.which('clang++')
    compiler_ok = False
    if compiler:
        probe = subprocess.run(['xcrun', '--find', 'clang++'], capture_output=True, text=True) if shutil.which('xcrun') else None
        compiler_ok = probe is not None and probe.returncode == 0
    check('compiler_sdk', compiler_ok, compiler or 'not found', 'Install Apple Command Line Tools with xcode-select --install.')
    app = Path('/Applications/OM Workspace.app')
    info = app / 'Contents/Info.plist'
    version = 'not installed'
    if info.exists():
        with info.open('rb') as stream:
            version = plistlib.load(stream).get('CFBundleVersion', 'unknown')
    check('workspace', info.exists(), version, 'Install OM Workspace yourself from the official vendor at /Applications/OM Workspace.app and review its terms.')
    check('native_build', (root / '.build/native/omrender').is_file(), root / '.build/native',
          'Run ./omrender build. The default deployment target is the tested macOS 27.2; older targets are unqualified.', False)
    optimizer = args.optimizer or args.adobe
    check('uv', shutil.which('uv'), shutil.which('uv') or 'not found', 'Install uv, then run uv sync --locked --project optimizer --python 3.12.', optimizer)
    check('exiftool', shutil.which('exiftool'), shutil.which('exiftool') or 'not found', 'Install ExifTool (for example: brew install exiftool).', optimizer)
    cms = ctypes.util.find_library('lcms2')
    check('littlecms2', cms, cms or 'not found', 'Install LittleCMS2 (for example: brew install little-cms2).', args.adobe)
    converter = Path('/Applications/Adobe DNG Converter.app/Contents/MacOS/Adobe DNG Converter')
    check('dng_converter', converter.is_file(), converter, 'Install Adobe DNG Converter from Adobe yourself; do not bundle the vendor app.', args.adobe)
    result = dict(schema='omrender-doctor/1', ok=all(c['available'] for c in checks if c['required']),
                  checks=checks, camera_operations=False, vendor_code_loaded=False,
                  tested_native_deployment_target='27.2', optimizer_python='>=3.12,<3.13',
                  fresh_mac_qualified=False)
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        for item in checks:
            state = 'OK' if item['available'] else 'MISSING' if item['required'] else 'OPTIONAL'
            print(f"{state:8} {item['name']}: {item['detail']}")
            if item['remedy']:
                print('         ' + item['remedy'])
        print('No camera operations or vendor code loading performed. Fresh-Mac qualification remains outstanding.')
    return 0 if result['ok'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
