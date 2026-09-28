"""Builds CHECKSUMS.txt and the release zip for a dist/TWK_MomentumEA_vX.Y folder.

usage (from the dist folder):  python build_package.py [folder] [zip name]
"""
import hashlib
import os
import sys
import zipfile

ROOT = sys.argv[1] if len(sys.argv) > 1 else 'TWK_MomentumEA_v1.1'
ZIP = sys.argv[2] if len(sys.argv) > 2 else ROOT + '_2026-09-25.zip'

files = sorted(
    os.path.relpath(os.path.join(d, f), ROOT).replace(os.sep, '\\')
    for d, _, fs in os.walk(ROOT) for f in fs if f != 'CHECKSUMS.txt'
)

with open(os.path.join(ROOT, 'CHECKSUMS.txt'), 'w', newline='\r\n') as out:
    out.write(f'SHA-256 checksums - {ROOT}\n')
    for rel in files:
        with open(os.path.join(ROOT, rel), 'rb') as fh:
            digest = hashlib.sha256(fh.read()).hexdigest().upper()
        out.write(f'{digest}  {rel}\n')

with zipfile.ZipFile(ZIP, 'w', zipfile.ZIP_DEFLATED) as z:
    for rel in files + ['CHECKSUMS.txt']:
        z.write(os.path.join(ROOT, rel), arcname=ROOT + '/' + rel.replace('\\', '/'))

with zipfile.ZipFile(ZIP) as z:
    print('zip:', ZIP, os.path.getsize(ZIP), 'bytes,', len(z.namelist()), 'files, corrupt member:', z.testzip())
    for name in z.namelist():
        print('  ', name)
