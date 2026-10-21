# Paper betting snapshot

Read-only Streamlit research view. **Paper only, unproven.** This app reads only local sanitized exports; it does not connect to the original service.

```bash
python3 -m pip install -r requirements.txt
python3 export_snapshot.py
streamlit run streamlit_app.py --server.headless true --server.port 8599
```

Use `python3 export_snapshot.py --src /path/to/master-betting` for a different source. Source code is never imported or executed. The exporter opens `data/master.db` using SQLite `mode=ro` and `query_only`, in one read transaction, and reads only named public JSON artifacts and the literal observed payout assignment. It never reads environment credential files. Output is staged and bounded below 20 MB; nested sensitive field names are removed and credential-shaped assignments are redacted.

Today's date and snapshot timestamp use America/Los_Angeles. Per-sport Props 50 and All 100 come from the latest frozen `list:top50_props:*` / `list:top100_all:*` version for that date. Their source is the scheduled pregame pick log, as described in `daily_top50.py`, `top_lists.py`, and the generated `data/lists/*.md` reports. No live list rebuilding or grading occurs. Missing today's lists are empty with notices; older lists are never silently substituted. Market-only rows stay unranked. Frozen rank remains visible when sorting. The 95% filter uses the displayed model probability, not raw probability. Missing calibration provenance is flagged as unknown.

Calibration and scorecard artifacts retain source timestamps and scoring policies. Graded picks/paper entries and first-version list grades are limited to 10,000 recent rows each. Repeated picks may be correlated; the outcome chart is descriptive. Original scorecards provide their own deduplication, settlement, and review rules. No new settlement or profitability claim is inferred here.

The All-In calculator supports 2–12 legs and observed multipliers. Observed two-pick slips override multiplication (including the 0.5×/0.6× pair paying 1.6×). Unobserved shields return unknown. Boost combinations beyond observed slips are labeled estimates. Joint break-even is 1 / total return; the equal per-leg illustration assumes independence. Same-game adjustments, voids, and actual betslip terms can change returns.

## Refresh and publish

`./publish.sh [--src /path/to/source]` exports again, commits changed `data/` files, then pushes to `origin`'s `main`. With no data changes it prints `no change`. Set up your own remote before using it. The snapshot timestamp normally makes each refresh change metadata. This project was committed locally; no remote was added and nothing was pushed.

## Validation

```bash
python3 -c 'import streamlit_app'
python3 - <<'PY'
from streamlit.testing.v1 import AppTest
app = AppTest.from_file('streamlit_app.py').run(timeout=60)
assert not app.exception
PY
```

Missing or invalid snapshot JSON displays empty states. Dependencies are Streamlit, pandas, and Plotly only.
