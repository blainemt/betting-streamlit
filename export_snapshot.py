"""Export bounded, sanitized public betting data without importing the source app."""
import argparse
import ast
import csv
import json
import re
import sqlite3
import tempfile
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent
SENSITIVE = re.compile(r'key|token|secret|password|credential|authorization|cookie', re.I)
VALUE = re.compile(r'(?:Bearer\s+\S+|sk-[A-Za-z0-9_-]{16,}|(?:api[_-]?key|access[_-]?token|password|secret)\s*[:=]\s*\S+)', re.I)
LIMIT = 20_000_000


def clean(value):
    if isinstance(value, dict):
        return {k: clean(v) for k, v in value.items() if not SENSITIVE.search(k)}
    if isinstance(value, list):
        return [clean(v) for v in value]
    if isinstance(value, str):
        return VALUE.sub('[redacted]', value)
    return value


def read_json(path, warnings):
    try:
        if path.stat().st_size > LIMIT:
            raise ValueError('input exceeds size limit')
        return clean(json.loads(path.read_text()))
    except (OSError, ValueError):
        warnings.append(f'Unavailable: {path.name}')
        return {}


def export(src):
    now = datetime.now(ZoneInfo('America/Los_Angeles'))
    day = now.date().isoformat()
    warnings = []
    outputs = {}
    for name, relative in [('gaps', 'gap_scan_latest.json'), ('calibration', 'iteration/model_calibration.json'),
                           ('scorecard', 'iteration/pick_scorecard.json'), ('dabble_payouts', 'dabble_payouts.json')]:
        outputs[name + '.json'] = read_json(src / 'data' / relative, warnings)
    # Parse only a literal assignment; never execute/import source application code.
    try:
        tree = ast.parse((src / 'dabble_payouts.py').read_text())
        observed = next(ast.literal_eval(n.value) for n in tree.body if isinstance(n, ast.Assign)
                        and any(isinstance(t, ast.Name) and t.id == 'OBSERVED_2PICK' for t in n.targets))
        outputs['dabble_payouts.json']['observed_2pick'] = [dict(multipliers=list(k), payout=v) for k, v in observed.items()]
    except (OSError, ValueError, SyntaxError, StopIteration):
        warnings.append('Observed payouts unavailable')
    lists, grades, picks = [], [], []
    db = src / 'data/master.db'
    if db.exists():
        with sqlite3.connect(db.resolve().as_uri() + '?mode=ro', uri=True, timeout=10) as c:
            c.row_factory = sqlite3.Row
            c.execute('PRAGMA query_only=ON')
            c.execute('BEGIN')
            tables = {r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            for sport in ('nba', 'nfl', 'nhl', 'mlb'):
                for kind, prefix, limit in [('props50', 'top50_props', 50), ('all100', 'top100_all', 100)]:
                    tag = f'list:{prefix}:{sport}'
                    s = c.execute('SELECT * FROM list_snapshots WHERE tag=? AND list_date=? ORDER BY version DESC LIMIT 1', (tag, day)).fetchone() if 'list_snapshots' in tables else None
                    item = dict(sport=sport, kind=kind, date=day, rows=[], market_only=[])
                    if s:
                        params = json.loads(s['params_json'] or '{}')
                        item.update(version=s['version'], created_at=s['created_at'], rows=json.loads(s['rows_json'])[:limit], market_only=params.get('market_only', [])[:100], rules=params.get('rules', {}))
                        for row in item['rows'] + item['market_only']:
                            if row.get('pick_log_id') and 'pick_log' in tables:
                                flags = c.execute('SELECT flags FROM pick_log WHERE id=?', (row['pick_log_id'],)).fetchone()
                                if flags: row['flags'] = json.loads(flags[0] or '[]')
                    else:
                        warnings.append(f'No frozen {sport} {kind} for {day}')
                    lists.append(item)
            if 'pick_log' in tables:
                cols = 'id shown_at league event_id player market selection line venue venue_price model_prob fair_prob result actual graded_at flags ranking_source angle line_clv prob_clv'.split()
                available = {r[1] for r in c.execute('PRAGMA table_info(pick_log)')}
                cols = [x for x in cols if x in available]
                picks = [dict(r) for r in c.execute('SELECT '+','.join(cols)+" FROM pick_log WHERE result IN ('win','loss','push') OR ranking_source='paper_leads' OR flags LIKE '%paper:%' ORDER BY id DESC LIMIT 10000")]
            if {'list_grades', 'list_snapshots'} <= tables:
                for r in c.execute('SELECT s.tag,s.list_date,s.version,g.idx,g.result,g.graded_at FROM list_grades g JOIN list_snapshots s ON s.id=g.snapshot_id WHERE s.version=1 ORDER BY s.list_date DESC LIMIT 10000'):
                    grades.append(dict(r))
    else:
        warnings.append('Source database unavailable')
    outputs.update({'top_lists.json': lists, 'graded_picks.json': picks, 'list_grades.json': grades})
    outputs['meta.json'] = dict(snapshot_at=now.isoformat(), timezone='America/Los_Angeles', date=day, warnings=warnings,
                                graded_pick_limit=10000, list_grades_policy='First frozen version only', read_only=True)
    data = ROOT / 'data'
    data.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(dir=ROOT) as tmp:
        staging = Path(tmp)
        for name, value in outputs.items():
            (staging / name).write_text(json.dumps(clean(value), ensure_ascii=False, indent=2, allow_nan=False) + '\n')
        with (staging / 'graded_picks.csv').open('w', newline='') as f:
            rows = clean(picks)
            writer = csv.DictWriter(f, fieldnames=list(rows[0]) if rows else ['result'])
            writer.writeheader()
            writer.writerows({k: json.dumps(v) if isinstance(v, (list, dict)) else v for k, v in r.items()} for r in rows)
        total = sum(p.stat().st_size for p in staging.iterdir())
        if total >= LIMIT: raise ValueError('Snapshot exceeds 20 MB; refusing to publish')
        for p in staging.iterdir(): p.replace(data / p.name)
    print(f'Snapshot {day}: {total:,} bytes; {len(warnings)} notices')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--src', type=Path, default=Path('/workspace/master-betting'))
    export(parser.parse_args().src)
