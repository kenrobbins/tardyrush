from flask import g
from consts import *

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

def grouper_id_to_int(gid):
    if gid == 'gametype':
        return StatsGrouperGametype
    if gid == 'map':
        return StatsGrouperMap
    if gid == 'competition':
        return StatsGrouperCompetition
    return StatsGrouperDefault

