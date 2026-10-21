import pytest
from export_snapshot import clean
from streamlit_app import alt_parlay, display_frame


def test_alt_parlay():
    assert alt_parlay([dict(hit_prob=.8, yes_ask=50), dict(hit_prob=.9, yes_ask=60)]) == pytest.approx(dict(model=.72, price=.3, payout=10/3))
    assert alt_parlay([])['payout'] is None


def test_sanitize_raw():
    data = clean(dict(rows=[dict(raw_p=.99, raw_model_prob=.99, hit_prob=.8, kalshi_ticker='T')]))
    assert data == dict(rows=[dict(hit_prob=.8, kalshi_ticker='T')])
    assert 'raw_p' not in display_frame([dict(raw_p=.99, hit_prob=.8)]).columns


def test_exports_frozen_alt50(tmp_path, monkeypatch):
    import export_snapshot as exporter
    import sqlite3
    import json
    from datetime import datetime
    from zoneinfo import ZoneInfo
    src = tmp_path/'source'; (src/'data').mkdir(parents=True)
    dest = tmp_path/'mirror'; dest.mkdir()
    day = datetime.now(ZoneInfo('America/Los_Angeles')).date().isoformat()
    with sqlite3.connect(src/'data/master.db') as c:
        c.execute('CREATE TABLE list_snapshots(tag,list_date,version,created_at,rows_json,params_json)')
        c.execute('INSERT INTO list_snapshots VALUES(?,?,?,?,?,?)', ('list:alt50:all',day,1,'now',json.dumps([dict(hit_prob=.8, raw_p=.99, kalshi_ticker='T', flags=['UNCALIBRATED'])]),json.dumps(dict(as_of='9 AM PT', verification=dict(candidates=1, verified=1)))))
    monkeypatch.setattr(exporter, 'ROOT', dest)
    exporter.export(src)
    data = json.loads((dest/'data/top_lists.json').read_text())
    item = next(x for x in data if x['sport']=='all' and x['kind']=='alt50')
    assert item['rows'][0]['kalshi_ticker'] == 'T'
    assert 'raw_p' not in item['rows'][0]
    assert item['as_of'] == '9 AM PT'
