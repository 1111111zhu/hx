#!/usr/bin/env python3
"""Prepare a template pair and check actual output packages. Python 3 stdlib only.

This helper does not render files or certify sources/visual appearance.
"""
import argparse
import hashlib
import json
import re
import shutil
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
A = '{http://schemas.openxmlformats.org/drawingml/2006/main}'
X = '{http://schemas.openxmlformats.org/spreadsheetml/2006/main}'


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def inventory(pptx, xlsx):
    result = {'pptx_sha256': digest(pptx), 'xlsx_sha256': digest(xlsx), 'tables': [], 'sheets': []}
    for path in (pptx, xlsx):
        with zipfile.ZipFile(path) as z:
            if z.testzip():
                raise ValueError('Corrupt Office package: ' + str(path))
    with zipfile.ZipFile(pptx) as z:
        for name in sorted(z.namelist()):
            if not re.fullmatch(r'ppt/slides/slide\d+\.xml', name):
                continue
            root = ET.fromstring(z.read(name))
            for i, table in enumerate(root.iter(A + 'tbl')):
                rows = [[ ''.join(t.text or '' for t in c.iter(A + 't'))
                          for c in row.findall(A + 'tc')] for row in table.findall(A + 'tr')]
                result['tables'].append({'part': name, 'table_index': i, 'rows': rows})
    with zipfile.ZipFile(xlsx) as z:
        result['sheets'] = [n.attrib['name'] for n in ET.fromstring(z.read('xl/workbook.xml')).iter(X + 'sheet')]
    return result


def prepare(args):
    pptx = Path(args.pptx) if args.pptx else ROOT / 'assets/templates/weekly-template.pptx'
    xlsx = Path(args.xlsx) if args.xlsx else ROOT / 'assets/templates/evidence-template.xlsx'
    if bool(args.pptx) != bool(args.xlsx):
        raise ValueError('Supply both template paths together.')
    data = inventory(pptx, xlsx)
    out = Path(args.output_dir)
    targets = [out / 'working.pptx', out / 'working.xlsx', out / 'pair_inventory.json']
    if any(p.exists() for p in targets):
        raise ValueError('Working files already exist; choose a fresh output directory.')
    out.mkdir(parents=True, exist_ok=True)
    shutil.copy2(pptx, targets[0])
    shutil.copy2(xlsx, targets[1])
    data['status'] = 'prepared'
    targets[2].write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({'status': 'prepared', 'files': [str(p) for p in targets]}, ensure_ascii=False))


def check(args):
    baseline = json.loads((Path(args.baseline_dir) / 'pair_inventory.json').read_text(encoding='utf-8'))
    pptx, xlsx = Path(args.pptx), Path(args.xlsx)
    current = inventory(pptx, xlsx)
    payload = json.loads(Path(args.items).read_text(encoding='utf-8'))
    items = payload if isinstance(payload, list) else payload['items']
    errors = []
    if not items:
        errors.append('No selected items; cannot certify an updated pair.')
    for kind in ('pptx', 'xlsx'):
        if current[kind + '_sha256'] == baseline[kind + '_sha256']:
            errors.append(kind + ' is unchanged from baseline.')
    cells = [cell for table in current['tables'] for row in table['rows'] for cell in row]
    with zipfile.ZipFile(xlsx) as z:
        links = set()
        for name in z.namelist():
            if name.startswith('xl/worksheets/_rels/') and name.endswith('.rels'):
                for rel in ET.fromstring(z.read(name)):
                    if rel.attrib.get('Type', '').endswith('/hyperlink'):
                        links.add(rel.attrib.get('Target', ''))
    for i, item in enumerate(items, 1):
        body = next((item[k] for k in ('first_paragraph_raw', 'canonical_text', 'source_content') if item.get(k)), '')
        url = next((item[k] for k in ('article_url', 'url', 'articleUrl') if item.get(k)), '')
        if not body or body not in cells:
            errors.append(f'Item {i}: complete source paragraph missing from native PPT table cell.')
        if not url or url not in links:
            errors.append(f'Item {i}: Excel hyperlink missing.')
    result = {'structural_status': 'failed' if errors else 'passed', 'errors': errors,
              'source_verification': 'not_checked', 'visual_qa': 'not_checked',
              'image_overlap': 'not_checked', 'scope_preservation': 'not_checked',
              'note': 'Requires source, same-block visible URL, image geometry and render checks before completed.'}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if errors:
        raise SystemExit(1)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    subs = parser.add_subparsers(dest='command', required=True)
    p = subs.add_parser('prepare', help='Copy bundled or supplied templates; inventory native table cells.')
    p.add_argument('--pptx')
    p.add_argument('--xlsx')
    p.add_argument('--output-dir', required=True)
    p.set_defaults(func=prepare)
    p = subs.add_parser('check', help='Reject missing/unchanged pair or unwritten selected text/URLs.')
    for flag in ('baseline-dir', 'pptx', 'xlsx', 'items'):
        p.add_argument('--' + flag, required=True)
    p.set_defaults(func=check)
    args = parser.parse_args()
    args.func(args)


if __name__ == '__main__':
    main()
