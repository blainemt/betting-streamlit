"""Standalone read-only snapshot viewer. No source app imports or connections."""
import json
import math
from pathlib import Path
import pandas as pd
import plotly.express as px
import streamlit as st

DATA = Path(__file__).resolve().parent / 'data'


def load(name, default=None):
    try:
        return json.loads((DATA / name).read_text())
    except (OSError, ValueError):
        return {} if default is None else default


def payout_for(table, multipliers):
    """Observed shield payouts take precedence; other shields remain unknown."""
    n = len(multipliers)
    if n == 2:
        pair = sorted(multipliers)
        for row in table.get('observed_2pick', []):
            if sorted(row['multipliers']) == pair:
                return row['payout'], 'Observed slip'
    if any(m < 1 for m in multipliers):
        return None, 'Unobserved shield pairing'
    base = table.get('all_in', {}).get(str(n))
    return (base * math.prod(multipliers), 'Standard table' if all(m == 1 for m in multipliers) else 'Multiplicative estimate; verify in betslip') if base else (None, 'Payout table unavailable')


def alt_parlay(rows):
    if not rows: return dict(model=None, price=None, payout=None)
    price = math.prod(r['yes_ask'] / 100 for r in rows)
    return dict(model=math.prod(r['hit_prob'] for r in rows), price=price, payout=1 / price)


def display_frame(rows):
    """Expose only the frozen ranking probability; legacy model_prob may be raw."""
    df = pd.json_normalize(rows)
    calibrated = next((k for k in ('hit_prob', 'prob', 'blended_prob') if k in df), None)
    if calibrated:
        df['Model %'] = df[[k for k in ('hit_prob', 'prob', 'blended_prob') if k in df]].bfill(axis=1).iloc[:, 0]
    return df.drop(columns=[k for k in df if k.split('.')[-1] in {
        'hit_prob', 'prob', 'blended_prob', 'model_prob', 'raw_model_prob',
        'p_if_plays', 'p_model', 'play_prob', 'probability'
    } or any(part.startswith('raw_') for part in k.split('.'))], errors='ignore')


def show_rows(rows, ranked=True):
    if not rows:
        st.info('No rows available for this snapshot or filter.')
        return
    df = display_frame(rows)
    def badges(r):
        flags = r.get('flags')
        if isinstance(flags, str):
            try: flags = json.loads(flags)
            except ValueError: flags = [flags]
        bits = list(flags or [])
        if r.get('check') is True: bits.append('⚠ likely model error / stale line')
        if r.get('market_disagrees') is True: bits.append('⚠ model disagrees with market')
        if not r.get('calibration') or 'uncalibrated' in str(r.get('calibration')).lower(): bits.append('⚠ uncalibrated / calibration unknown')
        return '; '.join(str(x) for x in bits)
    df['Flags'] = [badges(r) for r in rows]
    if not ranked: df['rank'] = 'Unranked'
    cols = [x for x in ['rank','game','start_pt','who','player','market_label','market','selection','line','venue','price_text','Model %','market_prob','break_even','gap','calibration','Flags','reason'] if x in df]
    st.dataframe(df[cols], hide_index=True, width='stretch', column_config={k: st.column_config.NumberColumn('Model %' if k == 'Model %' else k.replace('_',' ').title(), format='percent') for k in ['Model %','market_prob','break_even','gap']})


def main():
    st.set_page_config(page_title='Paper betting snapshot', page_icon='📊', layout='wide')
    st.markdown('<style>.block-container{padding:1.2rem;max-width:1450px} @media(max-width:640px){.block-container{padding:.6rem} h1{font-size:1.7rem}}</style>', unsafe_allow_html=True)
    meta = load('meta.json')
    st.warning('Paper only, unproven — probabilities have not established an edge against closing lines.')
    st.caption(f"Snapshot: {meta.get('snapshot_at', 'unavailable')} · America/Los_Angeles · read-only")
    st.title('Betting research snapshot')
    if meta.get('warnings'):
        with st.expander('Snapshot notices'): st.write(meta['warnings'])
    top, alt, gaps, record, calculator = st.tabs(['Top lists', 'Alt 50', 'Gaps', 'Calibration / track record', 'Dabble payout calculator'])
    with top:
        sport = st.selectbox('Sport', ['nba','nfl','nhl','mlb'], format_func=str.upper)
        kind = st.radio('List', ['props50','all100'], format_func=lambda v: 'Props 50' if v == 'props50' else 'All 100', horizontal=True)
        sort = st.selectbox('Sort by', ['Model %','Gap'])
        high = st.checkbox('Model 95%+')
        item = next((x for x in load('top_lists.json', []) if x['sport']==sport and x['kind']==kind), {})
        st.caption(f"List date: {item.get('date','unavailable')} · Version {item.get('version','—')} · Frozen {item.get('created_at','unavailable')}")
        rows = item.get('rows', [])
        if high: rows = [r for r in rows if (r.get('hit_prob', r.get('prob')) or 0) >= .95]
        field = 'hit_prob' if sort == 'Model %' else 'gap'
        rows = sorted(rows, key=lambda r: r.get(field) if r.get(field) is not None else -math.inf, reverse=True)
        show_rows(rows)
        st.caption('Rank is the original frozen rank. Gap is Model % minus price break-even. Model % is the calibrated probability including chance of playing.')
        st.subheader('Market-only · unranked')
        st.caption('These rows have no independent model probability and are excluded from the model filter and ranking.')
        show_rows(item.get('market_only', []), ranked=False)
    with alt:
        alt_sport = st.selectbox('Alt 50 sport', ['all', 'nba', 'nfl', 'nhl'], format_func=str.upper)
        item = next((x for x in load('top_lists.json', []) if x['sport'] == alt_sport and x['kind'] == 'alt50'), {})
        st.caption(f"As of {item.get('as_of') or 'unavailable'} · Version {item.get('version', '—')}")
        st.write('Verification:', item.get('verification') or {})
        rows = item.get('rows', [])
        if rows:
            frame = pd.DataFrame([{'Rank': r['rank'], 'Sport': r['league'].upper(), 'Player / market': r['who'],
                'Strike': r['strike'], 'Game': r['game'], 'Start PT': r['start_pt'], 'Model %': r['hit_prob'],
                'Kalshi YES ask (¢)': r['yes_ask'], 'Kalshi implied %': r['implied'], 'Gap': r['gap'],
                'Flags': ', '.join(r['flags']), 'Kalshi ticker': r['kalshi_ticker']} for r in rows])
            st.dataframe(frame, hide_index=True, column_config={k: st.column_config.NumberColumn(format='percent') for k in ['Model %', 'Kalshi implied %', 'Gap']})
        else: st.info('No frozen Alt 50 rows available.')
        chosen = st.multiselect('Parlay legs', list(range(len(rows))), format_func=lambda i: f"{rows[i]['rank']}. {rows[i]['who']} {rows[i]['strike']} · {rows[i]['game']}")
        result = alt_parlay([rows[i] for i in chosen])
        if chosen:
            st.write(f"Combined Model %: {result['model']:.2%} · Combined Kalshi price: {result['price']*100:.2f}¢ · Payout per $1: ${result['payout']:.2f}")
        st.caption('same-game legs are correlated; product assumes independence')
    with gaps:
        data = load('gaps.json')
        st.caption(f"Scan: {data.get('at','unavailable')} · compared {data.get('compared',0)}")
        st.info('Scan gaps compare the reference market with venue break-even; they are not demonstrated model edges. Adjusted Dabble prices may have unknown payouts.')
        rows = data.get('gaps', [])
        if rows: st.dataframe(display_frame(rows), hide_index=True, width='stretch')
        else: st.info('No gap scan available.')
    with record:
        cal = load('calibration.json')
        st.caption(cal.get('rule', 'Calibration data unavailable.'))
        st.write(f"Graded calibration legs: {cal.get('legs',0)} · Brier: {cal.get('brier','—')}")
        buckets = pd.DataFrame(cal.get('buckets', []))
        if not buckets.empty and {'n','mean_prob','hit_rate'} <= set(buckets):
            valid = buckets[buckets.n > 0]
            if not valid.empty:
                fig = px.scatter(valid, x='mean_prob', y='hit_rate', size='n', hover_data=['n'], range_x=[0,1], range_y=[0,1], labels={'mean_prob':'Mean predicted probability','hit_rate':'Observed hit rate'})
                fig.add_shape(type='line', x0=0,y0=0,x1=1,y1=1, line=dict(dash='dash'))
                st.plotly_chart(fig, width='stretch')
            st.dataframe(buckets, hide_index=True, width='stretch')
        score = load('scorecard.json')
        st.subheader('Paper-angle scorecard')
        angles = score.get('groups', {}).get('angle', {})
        paper = [dict(angle=k, **v) for k,v in angles.items() if k.startswith('paper:')]
        if paper: st.dataframe(pd.json_normalize(paper), hide_index=True, width='stretch')
        else: st.info('Paper-angle scorecard unavailable.')
        st.caption(f"Scorecard generated: {score.get('at','unavailable')}")
        for note in score.get('limitations', []): st.caption(note)
        results = pd.DataFrame(load('graded_picks.json', []))
        if not results.empty and 'result' in results:
            settled = results[results.result.isin(['win','loss','push'])]
            if not settled.empty: st.plotly_chart(px.histogram(settled, x='result', color='result', title='Exported frozen pick outcomes (may include repeated legs)'), width='stretch')
            st.dataframe(display_frame(results.to_dict("records")), hide_index=True, width='stretch')
        else: st.info('No graded pick results available.')
        st.caption('Results export is capped at 10,000 recent records. Scorecard and calibration use their source policies; repeated picks are not independent trials.')
        with st.expander('Official list grades · version 1'):
            st.dataframe(pd.DataFrame(load('list_grades.json', [])), hide_index=True, width='stretch')
    with calculator:
        st.caption('All-In entries · total return includes stake · no same-game reductions or voids assumed. The operator betslip is authoritative.')
        table = load('dabble_payouts.json')
        n = st.selectbox('Leg count', list(range(2,13)))
        multipliers = []
        columns = st.columns(2)
        for i in range(n):
            with columns[i % 2]: multipliers.append(st.selectbox(f'Leg {i+1} multiplier', [1.0,.5,.6,.7,.9,1.1,1.2,1.5], key=f'leg_{i}'))
        payout, status = payout_for(table, multipliers)
        st.caption(status)
        if payout:
            a,b = st.columns(2)
            a.metric('Total return per $1 stake', f'{payout:g}×')
            b.metric('Joint break-even probability', f'{1/payout:.2%}')
            st.caption(f'Equal independent per-leg break-even: {(1/payout)**(1/n):.2%}. Joint break-even itself does not assume independence.')
        else: st.warning('⚠ Unknown payout: unobserved shield pairings cannot be calculated safely, or the payout table is missing.')
        with st.expander('Observed two-leg slips'):
            st.dataframe(pd.DataFrame(table.get('observed_2pick', [])), hide_index=True, width='stretch')


if __name__ == '__main__':
    main()
