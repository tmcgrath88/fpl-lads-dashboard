from fpl_api import (
    get_bootstrap,
    get_entry_history,
    get_entry_picks,
    get_event_live,
    get_month_to_events,
    get_playable_events,
)

PROMOTED_TEAMS_SEPTEMBER = ["Ipswich Town", "Hull City", "Coventry City"]
LONDON_TEAMS = ["Arsenal", "Chelsea", "Crystal Palace", "Fulham", "Spurs", "Brentford", "West Ham"]

# Irish / Scottish / Welsh players eligible for the March rule, confirmed against
# the live FPL player pool by (first_name, second_name) - matched by element id
# rather than name/web_name, since several web_names collide with unrelated
# players (e.g. three different players share the web_name "Wilson").
# Not sourced from the FPL API itself (it has no nationality field) - this list
# came from the league and was cross-checked against this season's squads.
# The following names supplied by the league were NOT found in this season's
# player pool and are excluded: Eiran Cashin, Alan Browne, Tayo Adaramola,
# Billy Gilmour, Jordan James.
IRISH_SCOTTISH_WELSH_PLAYERS = [
    ("Caoimhín", "Kelleher"), ("Nathan", "Collins"), ("Evan", "Ferguson"), ("Mark", "Travers"),
    ("Jake", "O'Brien"), ("John", "Egan"), ("Dara", "O'Shea"), ("Kasey", "McAteer"),
    ("Jack", "Taylor"), ("Chiedozie", "Ogbene"),
    ("John", "McGinn"), ("Andrew", "Robertson"), ("Ryan", "Christie"), ("Aaron", "Hickey"),
    ("Nathan", "Patterson"), ("Ben", "Gannon-Doak"),
    ("Brennan", "Johnson"), ("Neco", "Williams"), ("Harry", "Wilson"), ("Daniel", "James"),
    ("Joe", "Rodon"), ("Ben", "Davies"), ("Lewis", "Koumas"), ("Ethan", "Ampadu"),
]


def _resolve_player_ids(name_pairs):
    bs = get_bootstrap()
    ids = []
    for first, last in name_pairs:
        match = next(
            (e for e in bs["elements"] if e["first_name"] == first and e["second_name"] == last),
            None,
        )
        if match:
            ids.append(match["id"])
    return ids


def rule_team_points(entry_ids, events, team_names, scope="starting_xi"):
    """Total points scored by players from `team_names`, for each entry, summed over `events`.

    scope="starting_xi": only picks with multiplier > 0 (bench excluded, autosubs
    already reflected by FPL in the multiplier field). Captain/triple-captain
    multipliers are applied as FPL scored them.
    """
    bs = get_bootstrap()
    team_id_by_name = {t["name"]: t["id"] for t in bs["teams"]}
    target_team_ids = {team_id_by_name[n] for n in team_names if n in team_id_by_name}
    elem_team = {e["id"]: e["team"] for e in bs["elements"]}
    elem_name = {e["id"]: e["web_name"] for e in bs["elements"]}

    live_points = {}
    for ev in events:
        live = get_event_live(ev)
        live_points[ev] = {el["id"]: el["stats"]["total_points"] for el in live["elements"]}

    results = {}
    breakdown = {}
    for entry_id in entry_ids:
        total = 0
        lines = []
        for ev in events:
            picks = get_entry_picks(entry_id, ev)
            for p in picks["picks"]:
                mult = p["multiplier"]
                if scope == "starting_xi" and mult == 0:
                    continue
                if scope == "full_squad" and mult == 0:
                    mult = 1
                team_id = elem_team[p["element"]]
                if team_id in target_team_ids:
                    pts = live_points[ev].get(p["element"], 0) * mult
                    total += pts
                    lines.append((ev, elem_name[p["element"]], pts))
        results[entry_id] = total
        breakdown[entry_id] = lines
    return results, breakdown


def rule_player_ids_points(entry_ids, events, element_ids, scope="starting_xi"):
    """Same as rule_team_points but filtering by exact player id instead of club.

    Filtering by id (rather than name/web_name) avoids collisions between
    different players who happen to share a surname or web_name.
    """
    bs = get_bootstrap()
    elem_in_scope = set(element_ids)
    elem_name = {e["id"]: e["web_name"] for e in bs["elements"]}

    live_points = {}
    for ev in events:
        live = get_event_live(ev)
        live_points[ev] = {el["id"]: el["stats"]["total_points"] for el in live["elements"]}

    results = {}
    breakdown = {}
    for entry_id in entry_ids:
        total = 0
        lines = []
        for ev in events:
            picks = get_entry_picks(entry_id, ev)
            for p in picks["picks"]:
                mult = p["multiplier"]
                if scope == "starting_xi" and mult == 0:
                    continue
                if scope == "full_squad" and mult == 0:
                    mult = 1
                if p["element"] in elem_in_scope:
                    pts = live_points[ev].get(p["element"], 0) * mult
                    total += pts
                    lines.append((ev, elem_name[p["element"]], pts))
        results[entry_id] = total
        breakdown[entry_id] = lines
    return results, breakdown


def rule_overall_score(entry_ids, events):
    """Sum of each entry's official gameweek score (net of transfer hits) over `events`."""
    results = {}
    breakdown = {}
    for entry_id in entry_ids:
        hist = get_entry_history(entry_id)
        by_event = {h["event"]: h["points"] for h in hist["current"]}
        total = sum(by_event.get(ev, 0) for ev in events)
        results[entry_id] = total
        breakdown[entry_id] = [(ev, by_event[ev]) for ev in events if ev in by_event]
    return results, breakdown


def rule_fixed_gameweek_score(entry_ids, fixed_event):
    """Official score for one specific gameweek, ignoring whatever `events` the month maps to."""
    if fixed_event not in get_playable_events():
        return (
            {eid: 0 for eid in entry_ids},
            {eid: [(f"GW{fixed_event}", "not played yet")] for eid in entry_ids},
        )
    return rule_overall_score(entry_ids, [fixed_event])


def rule_max_gameweek_score(entry_ids, events):
    """Each entry's single highest official gameweek score among `events`."""
    results = {}
    breakdown = {}
    for entry_id in entry_ids:
        hist = get_entry_history(entry_id)
        by_event = {h["event"]: h["points"] for h in hist["current"] if h["event"] in events}
        if by_event:
            best_event = max(by_event, key=by_event.get)
            results[entry_id] = by_event[best_event]
            breakdown[entry_id] = [(best_event, by_event[best_event])]
        else:
            results[entry_id] = 0
            breakdown[entry_id] = []
    return results, breakdown


def rule_captain_points(entry_ids, events):
    """Points contributed by whichever pick actually carried the armband each gameweek
    (multiplier >= 2), so an auto-promoted vice-captain is credited correctly."""
    bs = get_bootstrap()
    elem_name = {e["id"]: e["web_name"] for e in bs["elements"]}

    live_points = {}
    for ev in events:
        live = get_event_live(ev)
        live_points[ev] = {el["id"]: el["stats"]["total_points"] for el in live["elements"]}

    results = {}
    breakdown = {}
    for entry_id in entry_ids:
        total = 0
        lines = []
        for ev in events:
            picks = get_entry_picks(entry_id, ev)
            for p in picks["picks"]:
                mult = p["multiplier"]
                if mult >= 2:
                    pts = live_points[ev].get(p["element"], 0) * mult
                    total += pts
                    lines.append((ev, elem_name[p["element"]], pts))
        results[entry_id] = total
        breakdown[entry_id] = lines
    return results, breakdown


def rule_bench_points(entry_ids, events):
    """Sum of points left on the bench over `events`."""
    results = {}
    breakdown = {}
    for entry_id in entry_ids:
        hist = get_entry_history(entry_id)
        by_event = {h["event"]: h["points_on_bench"] for h in hist["current"] if h["event"] in events}
        results[entry_id] = sum(by_event.values())
        breakdown[entry_id] = list(by_event.items())
    return results, breakdown


def rule_no_chip_score(entry_ids, events):
    """Sum of official gameweek scores over `events`, zeroed out entirely if any chip was used."""
    results = {}
    breakdown = {}
    for entry_id in entry_ids:
        hist = get_entry_history(entry_id)
        chips_used = [c["name"] for c in hist.get("chips", []) if c["event"] in events]
        by_event = {h["event"]: h["points"] for h in hist["current"] if h["event"] in events}
        if chips_used:
            results[entry_id] = 0
            breakdown[entry_id] = [(f"DISQUALIFIED (used {', '.join(chips_used)})", 0)]
        else:
            results[entry_id] = sum(by_event.values())
            breakdown[entry_id] = list(by_event.items())
    return results, breakdown


def _cumulative_points_at(entry_id, event_id):
    hist = get_entry_history(entry_id)
    by_event = {h["event"]: h["total_points"] for h in hist["current"]}
    valid = [e for e in by_event if e <= event_id]
    return by_event[max(valid)] if valid else 0


def rule_climb_since_jan1(entry_ids, events):
    """Places climbed in the league between Jan 1 and the latest played gameweek.

    Ignores the passed `events` (this isn't a per-gameweek sum) - it always compares
    the snapshot just before January's first gameweek against the most recent one played.
    """
    month_map = get_month_to_events()
    playable = set(get_playable_events())
    jan_key = next((m for m in month_map if m.endswith("-01")), None)

    if not jan_key or not playable:
        return {eid: 0 for eid in entry_ids}, {eid: [] for eid in entry_ids}

    baseline_event = min(month_map[jan_key]) - 1
    current_event = max(playable)

    baseline_pts = {eid: _cumulative_points_at(eid, baseline_event) for eid in entry_ids}
    current_pts = {eid: _cumulative_points_at(eid, current_event) for eid in entry_ids}

    baseline_order = sorted(entry_ids, key=lambda e: -baseline_pts[e])
    current_order = sorted(entry_ids, key=lambda e: -current_pts[e])
    baseline_rank = {eid: i + 1 for i, eid in enumerate(baseline_order)}
    current_rank = {eid: i + 1 for i, eid in enumerate(current_order)}

    results = {}
    breakdown = {}
    for eid in entry_ids:
        climb = baseline_rank[eid] - current_rank[eid]
        results[eid] = climb
        breakdown[eid] = [(f"Rank as of Jan 1 (GW{baseline_event}): {baseline_rank[eid]}",
                            f"Rank now (GW{current_event}): {current_rank[eid]}")]
    return results, breakdown


MONTH_RULES = {
    "August": {
        "description": "Highest total score for the month — standard FPL scoring, no restrictions.",
        "compute": lambda entry_ids, events: rule_overall_score(entry_ids, events),
    },
    "September": {
        "description": (
            "Total points scored by promoted-team players "
            "(Ipswich Town, Hull City, Coventry City) in each manager's starting XI. "
            "Standard FPL scoring — captain/TC multipliers and autosubs applied."
        ),
        "compute": lambda entry_ids, events: rule_team_points(
            entry_ids, events, PROMOTED_TEAMS_SEPTEMBER, scope="starting_xi"
        ),
    },
    "October": {
        "description": "Highest single gameweek score within the month (not summed across the month).",
        "compute": lambda entry_ids, events: rule_max_gameweek_score(entry_ids, events),
    },
    "November": {
        "description": (
            "Most points from the captained pick each gameweek (armband, doubled/tripled as scored — "
            "credited to the vice-captain if an autosub promotion occurred)."
        ),
        "compute": lambda entry_ids, events: rule_captain_points(entry_ids, events),
    },
    "December": {
        "description": "Highest score in Gameweek 17 only, regardless of December's other fixtures.",
        "compute": lambda entry_ids, events: rule_fixed_gameweek_score(entry_ids, 17),
    },
    "January": {
        "description": (
            "Total points scored by London-club players (Arsenal, Chelsea, Crystal Palace, Fulham, "
            "Spurs, Brentford, West Ham) in each manager's starting XI."
        ),
        "compute": lambda entry_ids, events: rule_team_points(entry_ids, events, LONDON_TEAMS, scope="starting_xi"),
    },
    "February": {
        "description": "Highest total points left on the bench for the month.",
        "compute": lambda entry_ids, events: rule_bench_points(entry_ids, events),
    },
    "March": {
        "description": "Highest points from Irish, Scottish and Welsh players.",
        "warning": (
            "5 names supplied by the league weren't found in this season's player pool and are "
            "excluded: Eiran Cashin, Alan Browne, Tayo Adaramola, Billy Gilmour, Jordan James."
        ),
        "compute": lambda entry_ids, events: rule_player_ids_points(
            entry_ids, events, _resolve_player_ids(IRISH_SCOTTISH_WELSH_PLAYERS), scope="starting_xi"
        ),
    },
    "April": {
        "description": (
            "Highest score for the month using no chips at all. "
            "If any chip (Wildcard, Free Hit, Bench Boost, Triple Captain) is used during "
            "the month, that manager scores 0 for April."
        ),
        "compute": lambda entry_ids, events: rule_no_chip_score(entry_ids, events),
    },
    "May": {
        "description": "Most league places climbed between January 1st and the latest completed gameweek.",
        "compute": lambda entry_ids, events: rule_climb_since_jan1(entry_ids, events),
    },
}
