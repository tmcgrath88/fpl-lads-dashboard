from datetime import datetime, timezone

import pandas as pd
import streamlit as st

from fpl_api import get_league_standings, get_month_to_events, get_playable_events
from rules import MONTH_RULES

LEAGUE_ID = 1012845

st.set_page_config(page_title="The Lads — FPL Monthly Table", page_icon="⚽", layout="centered")

st.markdown(
    """
    <style>
    .stApp { background-color: #37003c; }
    h1, h2, h3, p, span, label, .stMarkdown, .stCaption { color: #ffffff !important; }
    [data-testid="stSelectbox"] label { color: #e5e5e5 !important; }
    thead tr th { background-color: #4e0d5a !important; color: #ffffff !important; }
    tbody tr:nth-child(odd) { background-color: #2b0030 !important; }
    tbody tr:nth-child(even) { background-color: #37003c !important; }
    tbody tr td { color: #ffffff !important; }
    .rule-box {
        background-color: #4e0d5a;
        border-left: 4px solid #00ff87;
        padding: 12px 16px;
        border-radius: 6px;
        margin-bottom: 16px;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

st.title("⚽ The Lads — Monthly Table")

standings = get_league_standings(LEAGUE_ID)
league_name = standings["league"]["name"]
st.caption(f"League: {league_name} (ID {LEAGUE_ID})")

entries = {
    r["entry"]: {"manager": r["player_name"], "team": r["entry_name"]}
    for r in standings["standings"]["results"]
}

month_map = get_month_to_events()
month_options = sorted(month_map.keys())
month_labels = {m: pd.Period(m).strftime("%B %Y") for m in month_options}

col1, col2 = st.columns([3, 1])
with col1:
    current_month = datetime.now(timezone.utc).strftime("%Y-%m")
    if current_month in month_options:
        default_index = month_options.index(current_month)
    else:
        default_index = len(month_options) - 1 if month_options else 0
    selected = st.selectbox(
        "Select month",
        month_options,
        format_func=lambda m: month_labels[m],
        index=default_index,
    )
with col2:
    if st.button("🔄 Refresh"):
        st.cache_data.clear()
        st.rerun()

month_name = pd.Period(selected).strftime("%B")
events = month_map[selected]
playable = set(get_playable_events())
usable_events = [e for e in events if e in playable]
upcoming_events = [e for e in events if e not in playable]

gw_caption = "Gameweeks counted: " + ", ".join(f"GW{e}" for e in usable_events) if usable_events else "No gameweeks played yet this month."
if upcoming_events:
    gw_caption += "  |  Not yet started: " + ", ".join(f"GW{e}" for e in upcoming_events)
st.caption(gw_caption)

rule = MONTH_RULES.get(month_name)

if rule is None:
    st.info(f"No rule has been set for **{month_labels[selected]}** yet.")
elif not usable_events:
    st.info("This month's gameweeks haven't started yet — check back once the first deadline passes.")
else:
    st.markdown(f"<div class='rule-box'>📋 <b>Rule:</b> {rule['description']}</div>", unsafe_allow_html=True)

    with st.spinner("Pulling live data from the FPL API..."):
        results, breakdown = rule["compute"](list(entries.keys()), usable_events)

    rows = [
        {"Manager": entries[eid]["manager"], "Team": entries[eid]["team"], "Points": pts}
        for eid, pts in results.items()
    ]
    df = pd.DataFrame(rows).sort_values("Points", ascending=False).reset_index(drop=True)
    df.index += 1
    df.index.name = "Rank"

    st.dataframe(df, width="stretch")

    with st.expander("Show scoring breakdown per manager"):
        for eid, lines in breakdown.items():
            label = f"{entries[eid]['manager']} — {entries[eid]['team']} ({results[eid]} pts)"
            st.markdown(f"**{label}**")
            if lines:
                for ev, name, pts in lines:
                    st.write(f"GW{ev}: {name} = {pts} pts")
            else:
                st.write("_No qualifying players this month_")

st.caption("Data refreshes automatically every 60 seconds, or click Refresh for an instant pull.")
