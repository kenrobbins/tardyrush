from flask import g

def is_founder(team_id=None):
    if not g.user:
        return False
    if team_id is None:
        return len(g.founder_teams) > 0
    return team_id in g.founder_teams

def is_team_leader(team_id=None):
    if not g.user:
        return False
    if team_id is None:
        return len(g.team_leader_teams) > 0
    return team_id in g.team_leader_teams

def is_on_current_team(current_team_id):
    return current_team_id in g.teams

