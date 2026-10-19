"""Join the NYC DOE middle school directory (admissions method per program) to our SchoolDigger schools and write
data/school_geo/nyc_middle_directory.json, which defines each community district's middle school pool.

Source: NYC Public Schools InfoHub > Admissions and Enrollment > Directory Data (Fall 2026 middle school file).
  python3 -I scripts/catalog/build_nyc_middle_directory.py <ms directory xlsx> [--write] [district ...]
Without --write it only prints the matches and a per-district summary. Stdlib xlsx reader: no openpyxl needed.
Re-run each admissions cycle (the directory changes yearly)."""
import os, sys, gzip, json, re, zipfile, collections
import xml.etree.ElementTree as ET
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))  # repo root (works under python -I)
from data_sources.school_zones import _tokens, _nyc_name_for_dbn

NS = {'m': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}


def read_sheet(path, sheet='Data'):
    z = zipfile.ZipFile(path)
    ss = [''.join(t.text or '' for t in si.iter('{%s}t' % NS['m']))
          for si in ET.fromstring(z.read('xl/sharedStrings.xml')).findall('m:si', NS)]
    names = [s.get('name') for s in ET.fromstring(z.read('xl/workbook.xml')).find('m:sheets', NS)]
    i = names.index(sheet) + 1
    rows = []
    for r in ET.fromstring(z.read(f'xl/worksheets/sheet{i}.xml')).iter('{%s}row' % NS['m']):
        row = {}
        for c in r.findall('m:c', NS):
            col = re.match(r'[A-Z]+', c.get('r')).group()
            v = c.find('m:v', NS)
            if v is not None:
                row[col] = ss[int(v.text)] if c.get('t') == 's' else v.text
        rows.append(row)
    hdr = {k: v for k, v in rows[0].items()}
    return [{hdr[k]: v for k, v in r.items() if k in hdr} for r in rows[1:]]


SPECIAL = ('D75 Special Education Inclusive Services', 'ASD/ACES Program')


def methods_of(r):
    return [r[f'admissionsmethod_prog{i}'] for i in range(1, 16)
            if r.get(f'admissionsmethod_prog{i}') and r[f'admissionsmethod_prog{i}'] not in SPECIAL]


def klass(ms):
    open_ = any(m in ('Open', 'Zone Priority', 'Zoned Only') for m in ms)
    sel = any(m in ('Screened', 'Screened With Assessment', 'Audition', 'Talent Test') for m in ms)
    return 'mixed' if open_ and sel else 'selective' if sel else 'open' if open_ else 'other'


def load_sd():
    sd = json.load(gzip.open('data/school_snapshot/NY.json.gz'))['schools']
    by = collections.defaultdict(list)
    for s in sd:
        m = re.search(r'geographic district\s*#\s*(\d+)', (s.get('district') or {}).get('districtName', ''), re.I)
        if m and not s.get('isPrivate'):
            by[int(m.group(1))].append(s)
    return by


# directory DBNs whose school SchoolDigger lists under a different name, and rows that must not be matched
NAME_OVERRIDES = {'15K447': 'Exploratory School (The)'}
NO_MATCH = {'The Annex at John Dewey'}


def match(row, by):
    """(school, how): the SchoolDigger school for a directory row, by the NCES name behind its DBN, then by name tokens."""
    m = re.search(r'\((\d{2})([KMQXR])(\d{3})\)', row['name'])
    if not m:
        return None, None
    d, num = int(m.group(1)), int(m.group(3))
    cands = by.get(d, [])
    if re.sub(r'\s*\(.*', '', row['name']) in NO_MATCH:
        return None, None
    forced = NAME_OVERRIDES.get(f'{d:02d}{m.group(2)}{num:03d}')
    if forced:
        hit = [s for s in cands if s['schoolName'] == forced]
        return (hit[0], 'override') if hit else (None, None)
    want = [_tokens(_nyc_name_for_dbn(f'{d:02d}{m.group(2)}{num:03d}')),
            _tokens(re.sub(r'\(.*?\)', '', row['name']))]
    want = [w for w in want if w]
    for how, pick in (('nces_name', want[:1]), ('dir_name', want[-1:])):
        for w in pick:
            hit = [s for s in cands if _tokens(s['schoolName']) == w or w <= _tokens(s['schoolName'])]
            if len(hit) >= 1:
                return min(hit, key=lambda s: len(_tokens(s['schoolName']))), how
    best, bj = None, 0.0
    for s in cands:
        t = _tokens(s['schoolName'])
        for w in want:
            j = len(w & t) / max(1, len(w | t))
            if j > bj:
                best, bj = s, j
    if best is not None and bj >= 0.5:
        return best, 'overlap'
    return None, None


if __name__ == '__main__':
    rows = read_sheet(sys.argv[1])
    by = load_sd()
    out = []
    for r in rows:
        s, how = match(r, by)
        m = re.search(r'\((\d{2})', r['name'])
        if not m:
            continue
        rat = enr = None
        if s and s.get('rankHistory'):
            rat = s['rankHistory'][0].get('rankStatewidePercentage')
            enr = ((s.get('schoolYearlyDetails') or [{}])[0] or {}).get('numberOfStudents')
        if not methods_of(r):
            continue
        out.append(dict(d=int(m.group(1)), name=re.sub(r'\s*\(.*', '', r['name']), cls=klass(methods_of(r)),
                        methods=sorted(set(methods_of(r))), rating=rat, enr=enr, how=how, span=r.get('gradespan')))
    print('(special-education and autism-only programs are not counted as general-education access)')
    print('directory schools', len(out), '| matched to a school', sum(1 for o in out if o['how']),
          '| matched with a rating', sum(1 for o in out if o['rating'] is not None))
    if '--write' in sys.argv:
        bundle = []
        for r in rows:
            mm = re.search(r'\((\d{2})([KMQXR])(\d{3})\)', r['name'])
            ms = methods_of(r)
            if not mm or not ms:
                continue
            sc, how = match(r, by)
            bundle.append({'dbn': f'{mm.group(1)}{mm.group(2)}{mm.group(3)}', 'district': int(mm.group(1)),
                           'name': re.sub(r'\s*\(.*', '', r['name']), 'class': klass(ms), 'methods': sorted(set(ms)),
                           'span': r.get('gradespan'), 'schoolid': sc['schoolid'] if sc else None, 'match': how})
        dest = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                            'data', 'school_geo', 'nyc_middle_directory.json')
        json.dump({'source': 'NYC Public Schools InfoHub directory data, Fall 2026 middle schools', 'schools': bundle},
                  open(dest, 'w'), indent=0)
        print('wrote', dest, len(bundle), 'schools')
    for d in [int(x) for x in sys.argv[2:] if x.isdigit()]:
        print(f'\nDistrict {d}')
        grp = collections.defaultdict(list)
        for o in out:
            if o['d'] == d:
                grp[o['cls']].append(o)
        for c in ('open', 'mixed', 'selective', 'other'):
            g = grp.get(c, [])
            rated = [o for o in g if o['rating'] is not None]
            w = sum(o['enr'] or 1 for o in rated)
            avg = round(sum(o['rating'] * (o['enr'] or 1) for o in rated) / w) if rated else None
            print(f'  {c:10} {len(g):>2} schools, {len(rated):>2} rated, weighted avg {avg}')
        for o in sorted(out, key=lambda o: -(o['rating'] or -1)):
            if o['d'] == d:
                print(f"    {str(round(o['rating'])) if o['rating'] is not None else '--':>3} {o['cls']:9} {o['name'][:44]:44} {','.join(o['methods'])[:36]}")
