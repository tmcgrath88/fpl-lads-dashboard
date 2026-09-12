from fpl_api import get_bootstrap, get_event_live, get_entry_picks

PROMOTED_TEAMS_SEPTEMBER = ["Ipswich Town", "Hull City", "Coventry City"]


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


MONTH_RULES = {
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
}
