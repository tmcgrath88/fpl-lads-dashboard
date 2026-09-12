from datetime import datetime, timezone

import requests
import streamlit as st

BASE = "https://fantasy.premierleague.com/api"
HEADERS = {"User-Agent": "Mozilla/5.0"}


@st.cache_data(ttl=3600)
def get_bootstrap():
    r = requests.get(f"{BASE}/bootstrap-static/", headers=HEADERS, timeout=15)
    r.raise_for_status()
    return r.json()


@st.cache_data(ttl=1800)
def get_fixtures(event):
    r = requests.get(f"{BASE}/fixtures/", params={"event": event}, headers=HEADERS, timeout=15)
    r.raise_for_status()
    return r.json()


@st.cache_data(ttl=60)
def get_league_standings(league_id):
    r = requests.get(f"{BASE}/leagues-classic/{league_id}/standings/", headers=HEADERS, timeout=15)
    r.raise_for_status()
    return r.json()


@st.cache_data(ttl=60)
def get_event_live(event):
    r = requests.get(f"{BASE}/event/{event}/live/", headers=HEADERS, timeout=15)
    r.raise_for_status()
    return r.json()


@st.cache_data(ttl=60)
def get_entry_picks(entry_id, event):
    r = requests.get(f"{BASE}/entry/{entry_id}/event/{event}/picks/", headers=HEADERS, timeout=15)
    r.raise_for_status()
    return r.json()


@st.cache_data(ttl=1800)
def get_month_to_events():
    """Map 'YYYY-MM' -> sorted gameweek ids that have at least one fixture in that month."""
    bs = get_bootstrap()
    month_map = {}
    for ev in bs["events"]:
        fixtures = get_fixtures(ev["id"])
        months = {f["kickoff_time"][:7] for f in fixtures if f.get("kickoff_time")}
        for m in months:
            month_map.setdefault(m, []).append(ev["id"])
    for m in month_map:
        month_map[m] = sorted(set(month_map[m]))
    return month_map


@st.cache_data(ttl=60)
def get_playable_events():
    """Gameweek ids whose deadline has already passed (picks are locked and queryable)."""
    bs = get_bootstrap()
    now = datetime.now(timezone.utc)
    playable = []
    for ev in bs["events"]:
        deadline = datetime.strptime(ev["deadline_time"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
        if deadline <= now:
            playable.append(ev["id"])
    return sorted(playable)
