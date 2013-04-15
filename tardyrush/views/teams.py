import datetime
import collections

from flask import Module, g, flash, url_for, request
from flask.ext.wtf import ValidationError
from tardyrush import db
from tardyrush.views import require_login
from tardyrush.helpers import rt, jsonify, abs_url_for, redirect
from tardyrush.helpers.filters import *
from tardyrush.helpers.consts import *
from tardyrush.helpers.teams import grouper_id_to_int
from tardyrush.models import \
        Team, TeamForm, TeamPlayersForm, LeaveTeamForm, JoinTeamForm, \
        CompletedMatch, CompletedMatchPlayer, CompletedMatchRound, \
        MatchPlayer, Match, GameType, Map, Game, PlayerStatsCombineForm, \
        User, TeamPlayer, Competition
from matches import all as matches_all

from werkzeug.datastructures import ImmutableMultiDict

teams = Module(__name__)

@teams.route('/team/all/')
def all():
    if g.user.is_on_team():
        team_id = g.user.one_team.id
        team = Team(id=team_id)
    else:
        team = None

    return rt('teams/table.html',
            page={'top':'teams', 'sub':'all_teams'},
            all_teams=True,
            team=team,
            teams=Team.query.order_by(Team.name.asc()).all())

# show teams the current user is on
@teams.route('/team/')
def my_teams():
    if g.user.is_on_team():
        return show()

    return redirect(url_for('all'))

@teams.route('/team/<action>/', defaults={'team_id':-1}, methods=('GET','POST'))
@teams.route('/team/<int:team_id>/', defaults={'action':''})
@teams.route('/team/<int:team_id>/<action>/', methods=('GET','POST'))
def show(team_id=-1, action=''):
    page = { 'top' : 'team', 'sub' : 'main' }

    if team_id and type(team_id) == int:
        if team_id == -1:
            team_id = g.user.one_team.id
            page = {'top':'my_teams', 'sub':'all_my'}
        elif g.user.is_on_team(team_id):
            page = {'top':'my_teams', 'sub':'all_my'}

        if team_id == -1:
            if not g.user.is_guest:
                team_players = TeamPlayer.query.options(eagerload('team')).\
                        filter_by(user_id=g.user.id).\
                        order_by(TeamPlayer.status.asc()).\
                        all()
                teams = [ t.team for t in team_players ]
                return rt('teams/table.html',
                        page={'top':'my_teams', 'sub':'all_my'},
                        teams=teams)
            return redirect(url_for('all'))

        if team_id > 0:
            team = Team.query.filter_by(id=team_id).first()
        else:
            team = None

        if not team:
            flash(u'Team not found', 'error')
            return redirect(url_for('all'))

        if action == 'join':
            if not g.user:
                flash(u'You must be signed in to join a team.', 'error')
            elif g.user.is_on_team(team_id):
                flash(u'You are already on this team.', 'info')
            elif g.user.is_on_team():
                flash(u'You are already on a team.  Leave your current team '
                       'first before joining this team.', 'error')
            else:
                join_form = JoinTeamForm(request.form)

                def validate_password(form, field):
                    if field.data != team.join_password:
                        raise ValidationError(\
                                u"The password you entered is incorrect.")

                JoinTeamForm.validate_password = validate_password

                if join_form.validate_on_submit():
                    tp = TeamPlayer(user_id=g.user.id,
                                    team_id=team.id,
                                    date_joined=datetime.datetime.utcnow(),
                                    status=TeamPlayer.StatusNormal)
                    db.session.add(tp)
                    db.session.commit()
                    flash(u'You have successfully joined this team.', 'success')

                return redirect(url_for('show', team_id=team.id))

        elif action == 'leave':
            if not g.user:
                flash(u'You must be signed in to join a team.', 'error')
            elif not g.user.is_on_team(team_id):
                flash(u'You are not on this team.', 'error')
            else:
                leave_form = LeaveTeamForm(request.form)

                if leave_form.validate_on_submit():
                    # make sure there is still a founder on the team

                    skip = False
                    if team.id in g.user.founder_teams:
                        other_founders = False
                        for p in team.players:
                            if p.status == TeamPlayer.StatusFounder and \
                                    p.user_id != g.user.id:
                                other_founders = True
                                break

                        if not other_founders:
                            flash(u'You cannot leave this team because you '\
                                   'are the only founder.  Add another '\
                                   'founder first.', 'error')
                            skip = True

                    if not skip:
                        TeamPlayer.query.\
                                filter_by(team_id=team.id).\
                                filter_by(user_id=g.user.id).delete(False)

                        MatchPlayer.query.\
                                filter(MatchPlayer.match_id.in_(\
                                    db.session.query(Match.id).\
                                    filter_by(team_id=team.id))).\
                                filter_by(user_id=g.user.id).delete(False)
                        db.session.commit()
                        flash(u'You have successfully left this team.',
                              'success')
                        return redirect(url_for('show',team_id=team.id))

        # only edit or delete for own team if a team leader
        elif g.user.is_team_leader(team_id):
            if action == 'edit' and \
                    request.values.get('edit_players') == '1':
                action = 'edit_players'

            team_names = [ t.name.lower() for t in Team.query.all() ]
            if team.name.lower() in team_names:
                team_names.remove(team.name.lower())

            if action == 'edit':
                form = TeamForm(request.form, obj=team)
                players_form = TeamPlayersForm(ImmutableMultiDict(), obj=team)
            else:
                form = TeamForm(ImmutableMultiDict(), obj=team)
                players_form = TeamPlayersForm(request.form, obj=team)

            form.name.validators[0].values = team_names

            if action == 'edit':
                players = {}
                for p in team.players:
                    players[p.user_id] = p.user.name

                if not g.user.is_founder(team_id):
                    choices_no_founder = [ (s, n) for s, n in \
                            TeamPlayer.StatusChoices if s !=
                            TeamPlayer.StatusFounder ]

                    for f in players_form.players:
                        if f.status.data == TeamPlayer.StatusFounder:
                            f.delete.disabled = True
                            f.status.disabled = True
                            f.status.choices = [ (TeamPlayer.StatusFounder,
                                                  "Founder") ]
                        else:
                            f.status.choices = choices_no_founder

                if form.validate_on_submit():
                    form.populate_obj(team)
                    db.session.commit()
                    flash(u'The team was successfully updated.', 'success')
                    return redirect(url_for('show',
                        team_id=team.id, action='edit'))

                return rt('teams/create.html', team_id=team.id,
                        page={'top':'my_teams', 'sub':'edit'},
                        team=team,
                        players=players, form=form, players_form=players_form)
            elif action == 'edit_players':
                players = {}
                for p in team.players:
                    players[p.user_id] = p.user.name

                if not g.user.is_founder(team_id):
                    choices_no_founder = [ (s, n) for s, n in \
                            TeamPlayer.StatusChoices if s !=
                            TeamPlayer.StatusFounder ]

                    for f in players_form.players:
                        if f.status.data == TeamPlayer.StatusFounder:
                            f.delete.disabled = True
                            f.status.disabled = True
                            f.status.choices = [ (TeamPlayer.StatusFounder,
                                                  "Founder") ]
                        else:
                            f.status.choices = choices_no_founder

                if players_form.validate_on_submit():
                    founders = set([ p.user_id for p in team.players if
                        p.status==TeamPlayer.StatusFounder ])

                    new_statuses = {}
                    new_founders = set([f for f in founders])
                    editing_founders = False
                    deleting_founders = False
                    to_delete = []
                    for f in players_form.players:
                        if f.delete.data:
                            to_delete.append(f.user_id.data)
                            if f.user_id.data in founders:
                                new_founders.remove(f.user_id.data)
                                deleting_founders = True
                        elif f.status.data == TeamPlayer.StatusFounder:
                            new_founders.add(f.user_id.data)
                        else:
                            try:
                                new_founders.remove(f.user_id.data)
                            except:
                                pass

                        new_statuses[f.user_id.data] = f.status.data

                    if founders != new_founders:
                        editing_founders = True

                    save = True
                    if len(new_founders) < 1:
                        flash(u'There must be at least one founder on the '
                               'team.', 'error')
                        save = False

                    if team_id not in g.user.founder_teams and \
                            (editing_founders or deleting_founders):
                        flash(u'You must be a founder to edit or delete a '
                               'founder.', 'error')
                        save = False

                    if save:
                        for p in team.players:
                            if p.user_id in new_statuses:
                                p.status = new_statuses[p.user_id]

                        if len(to_delete):
                            TeamPlayer.query.filter_by(team_id=team_id).\
                                    filter(TeamPlayer.user_id.in_(to_delete)).\
                                    delete(False)
                            MatchPlayer.query.\
                                    filter_by(team_id=team_id).\
                                    filter(MatchPlayer.user_id.in_(to_delete)).\
                                    delete(False)

                        db.session.commit()
                        flash(u'The team was successfully updated.', 'success')
                        return redirect(url_for('show',
                            team_id=team.id, action='edit'))

                return rt('teams/create.html',
                        page={'top':'my_teams', 'sub':'edit'},
                        team_id=team.id, team=team,
                        players=players, form=form, players_form=players_form)

            elif action == 'delete':
                if request.method == 'POST':
                    db.session.delete(team)
                    db.session.commit()
                    flash(u'The team was successfuly deleted.', 'success')
                    return redirect(url_for('all'))

                flash(u"That team doesn't exist.", 'error')
                return redirect(url_for('show', team_id=team.id))

        elif action in ('delete', 'edit'):
            flash(u'You must be a team leader to edit the team.', 'error')

        join_form = None
        leave_form = None
        if not g.user.is_guest:
            if not g.user.is_on_team(team_id):
                join_form = JoinTeamForm()
            else:
                leave_form = LeaveTeamForm()

        cmatches = CompletedMatch.query.filter_by(team_id=team_id).all()

        wins = 0
        losses = 0
        draws = 0
        for c in cmatches:
            if c.wins > c.losses:
                wins += 1
            elif c.wins < c.losses:
                losses += 1
            else:
                draws += 1

        players = team.players.join(User).\
                order_by(TeamPlayer.status.asc()).\
                order_by(User.name.asc())

        return rt('teams/single.html',
                page=page,
                wins=wins, losses=losses, draws=draws,
                team=team,
                players=players,
                leave_form=leave_form,
                join_form=join_form)

    return redirect(url_for('all'))

@teams.route('/team/add', methods=('GET','POST'))
@require_login(page={'top':'teams','sub':'add_team'})
def add():
    if g.user.is_on_team():
        flash(u'You are already on a team.  Leave your current team first '
               'before creating a new one.', 'error')
        return redirect(url_for('my_teams'))

    team_names = [ t.name.lower() for t in Team.query.all() ]

    form = TeamForm()
    form.name.validators[0].values = team_names

    if form.validate_on_submit():
        team = Team(name=form.name.data,
                    tag=form.tag.data,
                    url=form.url.data,
                    date_created=datetime.datetime.utcnow(),
                    join_password=form.join_password.data)
        db.session.add(team)
        db.session.commit()

        # hmm, need to commit the team to get the team id
        team_player = TeamPlayer(team_id=team.id, user_id=g.user.id,
                                 status=TeamPlayer.StatusFounder)
        db.session.add(team_player)
        db.session.commit()

        flash(u'The team was successfully created.', 'success')
        return redirect(url_for('matches.my_matches'))

    return rt('teams/create.html',
            page={'top': 'teams', 'sub': 'add_team'},
            adding=True,
            form=form)

@teams.route('/team/<int:team_id>/matches/')
def matches(team_id=0):
    return matches_all(team_id)

@teams.route('/team/<int:team_id>/records/')
def records(team_id=0):
    if not g.user.is_on_team(team_id):
        return jsonify(success=False)

    api = request.values.get('api') == '1'

    team = Team.query.filter_by(id=team_id).first()

    if not team:
        return jsonify(success=False)

    match_id = request.values.get('match_id')
    match = Match.query.filter_by(id=match_id).first()

    if not match:
        return jsonify(success=False)

    ( opponent_rec, competition_rec, server_rec, opp_comp_rec ) = \
            match.historical_records()

    return jsonify(success=True, opponent_rec=opponent_rec,
            competition_rec=competition_rec, server_rec=server_rec,
            opp_comp_rec=opp_comp_rec)

@teams.route('/team/<int:team_id>/stats/')
def stats(team_id=0):
    team = Team.query.filter_by(id=team_id).first()

    if not team:
        return redirect(url_for('all'))

    if g.user.is_on_team(team_id):
        page = { 'top' : 'my_teams', 'sub' : 'player_stats' }
    else:
        page = { 'top' : 'team', 'sub' : 'player_stats' }

    # only look at one game at a time.  but the tables only have competition
    # id, so get the competition ids from the game id.
    game_id = request.values.get('game') or 1

    game = db.session.query(Game).filter_by(id=game_id).one()
    competitions = db.session.query(Competition.id,
                                    Competition.abbr,
                                    Competition.name).\
            filter_by(game_id=game_id).order_by(Competition.abbr).all()
    gametypes = db.session.query(GameType.id, GameType.name).\
            filter_by(game_id=game_id).\
            order_by(GameType.name).\
            all()
    maps = db.session.query(Map.id, Map.name).\
            filter_by(game_id=game_id).\
            order_by(Map.name).all()

    competition_ids = [ c.id for c in competitions ]

    combine_form = PlayerStatsCombineForm()
    combine_form.competition.choices = [ (0, "Competition"), (0, "Any") ]
    combine_form.gametype.choices = [ (0, "Game Type"), (0, "Any") ]
    combine_form.map.choices = [ (0, "Map"), (0, "Any") ]
    combine_form.competition.choices.extend([ (c.id, c.abbr) for c in\
        competitions ])
    combine_form.gametype.choices.extend([ (gt.id, gt.name) for gt in\
        gametypes ])
    combine_form.map.choices.extend([ (m.id, m.name) for m in\
        maps ])

    grouper_id = grouper_id_to_int(request.values.get('grouper'))

    if grouper_id == StatsGrouperGametype:
        grouper = CompletedMatchRound.gametype_id

        ghash = dict()
        for gt in gametypes:
            ghash[gt.id] = gt.name
    elif grouper_id == StatsGrouperMap:
        grouper = CompletedMatchRound.map_id

        ghash = dict()
        for m in maps:
            ghash[m.id] = m.name
    elif grouper_id == StatsGrouperCompetition:
        grouper = CompletedMatch.competition_id

        ghash = dict()
        for c in competitions:
            ghash[c.id] = c.name
    else:
        return redirect(url_for('stats', team_id=team_id))

    ##########################################################
    # fetch totals

    pcount_subquery = \
            db.session.query(CompletedMatchPlayer.user_id).\
            join((CompletedMatch,
                  CompletedMatchPlayer.cmatch_id == CompletedMatch.id)).\
            filter(CompletedMatch.team_id == team_id).\
            filter(CompletedMatch.competition_id.in_(competition_ids)).\
            group_by(CompletedMatchPlayer.cmatch_id).\
            group_by(CompletedMatchPlayer.user_id).\
            having(db.func.sum(CompletedMatchPlayer.kills) >=\
                   db.func.sum(CompletedMatchPlayer.deaths)).\
            with_entities(CompletedMatchPlayer.user_id).\
            subquery()

    positive_counts = db.engine.execute( \
            db.select(columns=['user_id', db.func.count()],\
                      from_obj=pcount_subquery).\
            group_by('user_id') )

    pcounts = dict()
    for p in positive_counts:
        pcounts[ p[0] ] = p[1]

    record_subquery = \
            db.session.query(CompletedMatchPlayer.user_id,
                             CompletedMatchPlayer.cmatch_id).\
            group_by(CompletedMatchPlayer.cmatch_id).\
            group_by(CompletedMatchPlayer.user_id).\
            with_entities(CompletedMatchPlayer.user_id,\
                          CompletedMatchPlayer.cmatch_id).\
            subquery()

    records = db.session.query(\
                               record_subquery.c.user_id,
                               db.func.sum(\
                                   db.cast(CompletedMatch.wins >\
                                           CompletedMatch.losses, db.INT)), \
                               db.func.sum(\
                                   db.cast(CompletedMatch.losses >\
                                           CompletedMatch.wins, db.INT))\
                              ).\
                         select_from(CompletedMatch).\
                         join((record_subquery,\
                               CompletedMatch.id ==\
                               record_subquery.c.cmatch_id\
                               )).\
                         filter(CompletedMatch.team_id == team_id).\
                         filter(CompletedMatch.competition_id.in_(competition_ids)).\
                         group_by(record_subquery.c.user_id)

    stats_pm = dict()
    for s in records:
        stats_pm[ s[0] ] = (s[1], s[2])

    stats_res = db.session.query(CompletedMatchPlayer.user_id,
                                 db.func.sum(CompletedMatchPlayer.kills),
                                 db.func.sum(CompletedMatchPlayer.deaths),
                                 db.func.sum(CompletedMatchPlayer.off_objs),
                                 db.func.sum(CompletedMatchPlayer.def_objs),
                                 db.func.sum(CompletedMatchPlayer.score),
                  db.func.count(db.func.distinct(CompletedMatch.id))).\
            join((CompletedMatch,
                  CompletedMatchPlayer.cmatch_id == CompletedMatch.id)).\
            filter(CompletedMatch.team_id == team_id).\
            filter(CompletedMatch.competition_id.in_(competition_ids)).\
            group_by(CompletedMatchPlayer.user_id).\
            all()

    total_stats = []
    for s in stats_res:
        w = 0
        l = 0
        pos_kdr = 0
        if s[0] in stats_pm:
            w, l = stats_pm[ s[0] ]
        if s[0] in pcounts:
            pos_kdr = pcounts[ s[0] ]
        if (w+l) == 0:
            ts = 0
        else:
            ts = float(s[3] + s[4]) / float(w+l)
        stats_item = { 'user_id' : s[0],
                       'kills' : s[1],
                       'deaths' : s[2],
                       'offobjs' : s[3],
                       'defobjs' : s[4],
                       'score' : s[5],
                       'team_score' : ts,
                       'wins' : w,
                       'losses' : l,
                       'pos_kdr' : pos_kdr
                     }
        total_stats.append(stats_item)

    ##########################################################


    pcount_subquery = \
            db.session.query(CompletedMatchPlayer.user_id,
                             grouper).\
            join((CompletedMatch,
                  CompletedMatchPlayer.cmatch_id == CompletedMatch.id)).\
            join((CompletedMatchRound,\
                  db.and_(\
                      CompletedMatchRound.cmatch_id == CompletedMatch.id,\
                      CompletedMatchRound.round_id ==\
                          CompletedMatchPlayer.round_id,\
                  ))).\
            filter(CompletedMatch.team_id == team_id).\
            filter(CompletedMatch.competition_id.in_(competition_ids)).\
            group_by(grouper).\
            group_by(CompletedMatchPlayer.cmatch_id).\
            group_by(CompletedMatchPlayer.user_id).\
            having(db.func.sum(CompletedMatchPlayer.kills) >=\
                   db.func.sum(CompletedMatchPlayer.deaths)).\
            with_entities(CompletedMatchPlayer.user_id,\
                          grouper).\
            subquery()

    positive_counts = db.engine.execute( \
            db.select(columns=['user_id', grouper.key, db.func.count()],\
                      from_obj=pcount_subquery).\
            group_by(grouper.key, 'user_id') )

    pcounts = dict()
    for p in positive_counts:
        pcounts[ (p[0], p[1]) ] = p[2]

    record_subquery = \
            db.session.query(CompletedMatchPlayer.user_id,
                             grouper,
                             CompletedMatchPlayer.cmatch_id).\
            join((CompletedMatchRound,\
                  db.and_(\
                      CompletedMatchRound.cmatch_id ==\
                          CompletedMatchPlayer.cmatch_id,\
                      CompletedMatchRound.round_id ==\
                          CompletedMatchPlayer.round_id,\
                  )))

    if grouper.key == 'competition_id':
        record_subquery = record_subquery.\
                filter(CompletedMatch.id == CompletedMatchPlayer.cmatch_id)

    record_subquery = record_subquery.\
            group_by(grouper).\
            group_by(CompletedMatchPlayer.cmatch_id).\
            group_by(CompletedMatchPlayer.user_id).\
            with_entities(CompletedMatchPlayer.user_id,
                          grouper,
                          CompletedMatchPlayer.cmatch_id).\
            subquery()

    records = db.session.query(\
                               record_subquery.c.user_id,
                               record_subquery.c.get(grouper.key),
                               db.func.sum(\
                                   db.cast(CompletedMatch.wins >\
                                           CompletedMatch.losses, db.INT)), \
                               db.func.sum(\
                                   db.cast(CompletedMatch.losses >\
                                           CompletedMatch.wins, db.INT))\
                              ).\
                         select_from(CompletedMatch).\
                         join((record_subquery,\
                               CompletedMatch.id ==\
                               record_subquery.c.cmatch_id\
                               )).\
                         filter(CompletedMatch.team_id == team_id).\
                         filter(CompletedMatch.competition_id.\
                                    in_(competition_ids)).\
                         group_by(record_subquery.c.get(grouper.key)).\
                         group_by(record_subquery.c.user_id)

    stats_pm = dict()
    for s in records:
        stats_pm[ (s[0], s[1]) ] = (s[2], s[3])

    stats_res = db.session.query(CompletedMatchPlayer.user_id,
                                 grouper,
                                 db.func.sum(CompletedMatchPlayer.kills),
                                 db.func.sum(CompletedMatchPlayer.deaths),
                                 db.func.sum(CompletedMatchPlayer.off_objs),
                                 db.func.sum(CompletedMatchPlayer.def_objs),
                                 db.func.sum(CompletedMatchPlayer.score),
                  db.func.count(db.func.distinct(CompletedMatch.id))).\
            join((CompletedMatch,
                  CompletedMatchPlayer.cmatch_id == CompletedMatch.id)).\
            join((CompletedMatchRound,\
                  db.and_(\
                      CompletedMatchRound.cmatch_id == CompletedMatch.id,\
                      CompletedMatchRound.round_id ==\
                          CompletedMatchPlayer.round_id,\
                  ))).\
            filter(CompletedMatch.team_id == team_id).\
            filter(CompletedMatch.competition_id.in_(competition_ids)).\
            group_by(grouper).\
            group_by(CompletedMatchPlayer.user_id).\
            all()

    stats = []
    for s in stats_res:
        w = 0
        l = 0
        pos_kdr = 0
        if (s[0], s[1]) in stats_pm:
            w, l = stats_pm[ (s[0], s[1]) ]
        if (s[0], s[1]) in pcounts:
            pos_kdr = pcounts[ (s[0], s[1]) ]
        if (w+l) == 0:
            ts = 0
        else:
            ts = float(s[4] + s[5]) / float(w+l)
        stats_item = { 'user_id' : s[0],
                       'grouper' : s[1],
                       'kills' : s[2],
                       'deaths' : s[3],
                       'offobjs' : s[4],
                       'defobjs' : s[5],
                       'score' : s[6],
                       'team_score' : ts,
                       'wins' : w,
                       'losses' : l,
                       'pos_kdr' : pos_kdr
                     }
        stats.append(stats_item)

    if grouper.key == 'competition_id':
        cmatches = db.session.query(grouper,
                CompletedMatch.id,
                CompletedMatch.wins,
                CompletedMatch.losses).\
                filter_by(team_id=team_id).\
                filter(CompletedMatch.competition_id.in_(competition_ids)).\
                filter(CompletedMatch.final_result_method !=\
                       CompletedMatch.FinalResultByForfeit).\
                all()
    else:
        cmatches = db.session.query(grouper,
                CompletedMatchRound.cmatch_id,
                CompletedMatch.wins,
                CompletedMatch.losses).\
                join(CompletedMatch).\
                filter_by(team_id=team_id).\
                filter(CompletedMatch.competition_id.in_(competition_ids)).\
                filter(CompletedMatch.final_result_method !=\
                       CompletedMatch.FinalResultByForfeit).\
                all()

    total_wins = 0
    total_losses = 0
    total_draws = 0
    seen_matches = set()
    seen_match_grouper = set()
    wins = collections.defaultdict(int)
    losses = collections.defaultdict(int)
    draws = collections.defaultdict(int)
    for c in cmatches:
        val = c[0]
        cmatch_id = c[1]
        if (cmatch_id, val) in seen_match_grouper:
            continue
        seen_match_grouper.add((cmatch_id, val))
        wins[val] += 0
        if c.wins > c.losses:
            wins[val] += 1
        elif c.wins < c.losses:
            losses[val] += 1
        else:
            draws[val] += 1

        if cmatch_id not in seen_matches:
            seen_matches.add(cmatch_id)
            if c.wins > c.losses:
                total_wins += 1
            elif c.wins < c.losses:
                total_losses += 1
            else:
                total_draws += 1

    phash = dict()
    for p in team.players:
        phash[p.user_id] = p.user.name

    return rt('teams/stats.html',
            page=page,
            game=game,
            combined=False,
            stats=stats,
            pcounts=pcounts,
            ghash=ghash,
            phash=phash,
            combine_form=combine_form,
            grouper=grouper.key[:-3],
            wins=wins, losses=losses, draws=draws,
            total_stats=total_stats,
            total_wins=total_wins, total_losses=total_losses,
            total_draws=total_draws,
            team=team)

@teams.route('/team/<int:team_id>/stats/combined/')
def combined_stats(team_id=0):
    team = Team.query.filter_by(id=team_id).first()

    if not team:
        return redirect(url_for('all'))

    if g.user.is_on_team(team_id):
        page = { 'top' : 'my_teams', 'sub' : 'player_stats' }
    else:
        page = { 'top' : 'team', 'sub' : 'player_stats' }

    game_id = request.values.get('game') or 1

    game = db.session.query(Game).filter_by(id=game_id).one()

    competitions = db.session.query(Competition.id, Competition.name).\
            filter_by(game_id=game_id).all()

    competition_ids = [ c.id for c in competitions ]

    gametype_id = int(request.values.get('gametype') or 0)
    map_id = int(request.values.get('map') or 0)
    competition_id = int(request.values.get('competition') or 0)

    competitions = db.session.query(Competition.id,
                                    Competition.abbr,
                                    Competition.name).\
            filter_by(game_id=game_id).order_by(Competition.abbr).all()
    gametypes = db.session.query(GameType.id, GameType.name).\
            order_by(GameType.name).\
            all()
    maps = db.session.query(Map.id, Map.name).order_by(Map.name).all()

    competition = next((v for v in competitions if v.id == competition_id), None)
    gametype = next((v for v in gametypes if v.id == gametype_id), None)
    mapp = next((v for v in maps if v.id == map_id), None)

    if not gametype and not mapp and not competition:
        return redirect(url_for('stats', team_id=team_id))

    combine_form = PlayerStatsCombineForm()
    combine_form.competition.choices = [ (0, "Competition"), (0, "Any") ]
    combine_form.gametype.choices = [ (0, "Game Type"), (0, "Any") ]
    combine_form.map.choices = [ (0, "Map"), (0, "Any") ]
    combine_form.competition.choices.extend([ (c.id, c.abbr) for c in\
        competitions ])
    combine_form.gametype.choices.extend([ (gt.id, gt.name) for gt in\
        gametypes ])
    combine_form.map.choices.extend([ (m.id, m.name) for m in\
        maps ])

    combine_form.competition.data = competition_id
    combine_form.gametype.data = gametype_id
    combine_form.map.data = map_id

    pcount_subquery = \
            db.session.query(CompletedMatchPlayer.user_id,
                             CompletedMatchRound.gametype_id,
                             CompletedMatchRound.map_id,
                             CompletedMatch.competition_id).\
            join((CompletedMatch,
                  CompletedMatchPlayer.cmatch_id == CompletedMatch.id)).\
            join((CompletedMatchRound,\
                  db.and_(\
                      CompletedMatchRound.cmatch_id == CompletedMatch.id,\
                      CompletedMatchRound.round_id ==\
                          CompletedMatchPlayer.round_id,\
                  ))).\
            filter(CompletedMatch.team_id == team_id)

    if gametype_id:
        pcount_subquery = pcount_subquery.filter_by(gametype_id=gametype_id)
    if map_id:
        pcount_subquery = pcount_subquery.filter_by(map_id=map_id)
    if competition_id:
        pcount_subquery = pcount_subquery.\
                filter(CompletedMatch.competition_id == competition_id)
    else:
        pcount_subquery = pcount_subquery.\
                filter(CompletedMatch.competition_id.in_(competition_ids))

    pcount_subquery = pcount_subquery.\
            group_by(CompletedMatchPlayer.cmatch_id).\
            group_by(CompletedMatchPlayer.user_id).\
            having(db.func.sum(CompletedMatchPlayer.kills) >=\
                   db.func.sum(CompletedMatchPlayer.deaths)).\
            with_entities(CompletedMatchPlayer.user_id).\
            subquery()

    positive_counts = db.engine.execute( \
            db.select(columns=['user_id', db.func.count()],\
                      from_obj=pcount_subquery).\
            group_by('user_id') )

    pcounts = dict()
    for p in positive_counts:
        pcounts[ p[0] ] = p[1]

    record_subquery = \
            db.session.query(CompletedMatchPlayer.user_id,
                             CompletedMatch.competition_id,
                             CompletedMatchPlayer.cmatch_id).\
            join((CompletedMatchRound,\
                  db.and_(\
                      CompletedMatchRound.cmatch_id ==\
                          CompletedMatchPlayer.cmatch_id,\
                      CompletedMatchRound.round_id ==\
                          CompletedMatchPlayer.round_id,\
                  )))

    if gametype_id:
        record_subquery = record_subquery.filter_by(gametype_id=gametype_id)
    if map_id:
        record_subquery = record_subquery.filter_by(map_id=map_id)
    if competition_id:
        record_subquery = record_subquery.\
                filter(CompletedMatch.competition_id == competition_id)

    record_subquery = record_subquery.\
            filter(CompletedMatch.id == CompletedMatchPlayer.cmatch_id).\
            group_by(CompletedMatchPlayer.cmatch_id).\
            group_by(CompletedMatchPlayer.user_id).\
            with_entities(CompletedMatchPlayer.user_id,
                          CompletedMatchPlayer.cmatch_id).\
            subquery()

    records = db.session.query(\
                               record_subquery.c.user_id,
                               db.func.sum(\
                                   db.cast(CompletedMatch.wins >\
                                           CompletedMatch.losses, db.INT)), \
                               db.func.sum(\
                                   db.cast(CompletedMatch.losses >\
                                           CompletedMatch.wins, db.INT))\
                              ).\
                         select_from(CompletedMatch).\
                         join((record_subquery,\
                               CompletedMatch.id ==\
                               record_subquery.c.cmatch_id\
                               )).\
                         filter(CompletedMatch.team_id == team_id).\
                         filter(CompletedMatch.competition_id.\
                                    in_(competition_ids)).\
                         group_by(record_subquery.c.user_id)

    stats_pm = dict()
    for s in records:
        stats_pm[ s[0] ] = (s[1], s[2])

    stats_res = db.session.query(CompletedMatchPlayer.user_id,
                                 db.func.sum(CompletedMatchPlayer.kills),
                                 db.func.sum(CompletedMatchPlayer.deaths),
                                 db.func.sum(CompletedMatchPlayer.off_objs),
                                 db.func.sum(CompletedMatchPlayer.def_objs),
                                 db.func.sum(CompletedMatchPlayer.score),
                  db.func.count(db.func.distinct(CompletedMatch.id))).\
            join((CompletedMatch,
                  CompletedMatchPlayer.cmatch_id == CompletedMatch.id)).\
            join((CompletedMatchRound,\
                  db.and_(\
                      CompletedMatchRound.cmatch_id == CompletedMatch.id,\
                      CompletedMatchRound.round_id ==\
                          CompletedMatchPlayer.round_id,\
                  ))).\
            filter(CompletedMatch.team_id == team_id)

    if gametype_id:
        stats_res = stats_res.filter_by(gametype_id=gametype_id)
    if map_id:
        stats_res = stats_res.filter_by(map_id=map_id)
    if competition_id:
        stats_res = stats_res.\
                filter(CompletedMatch.competition_id == competition_id)
    else:
        stats_res = stats_res.\
                filter(CompletedMatch.competition_id.in_(competition_ids))

    stats_res = stats_res.\
            group_by(CompletedMatchPlayer.user_id).\
            all()

    stats = []
    for s in stats_res:
        w = 0
        l = 0
        pos_kdr = 0
        if s[0] in stats_pm:
            w, l = stats_pm[ s[0] ]
        if s[0] in pcounts:
            pos_kdr = pcounts[ s[0] ]
        if (w+l) == 0:
            ts = 0
        else:
            ts = float(s[3] + s[4]) / float(w+l)
        stats_item = { 'user_id' : s[0],
                       'kills' : s[1],
                       'deaths' : s[2],
                       'offobjs' : s[3],
                       'defobjs' : s[4],
                       'score' : s[5],
                       'team_score' : ts,
                       'wins' : w,
                       'losses' : l,
                       'pos_kdr' : pos_kdr
                     }
        stats.append(stats_item)

    # team record

    cmatches = db.session.query(\
            CompletedMatchRound.cmatch_id,
            CompletedMatch.wins,
            CompletedMatch.losses,\
            CompletedMatch.final_result_method).\
            join(CompletedMatch).\
            filter_by(team_id=team_id).\
            filter(CompletedMatch.final_result_method !=\
                   CompletedMatch.FinalResultByForfeit)

    if gametype_id:
        cmatches = cmatches.\
                filter(CompletedMatchRound.gametype_id == gametype_id)
    if map_id:
        cmatches = cmatches.\
                filter(CompletedMatchRound.map_id == map_id)
    if competition_id:
        cmatches = cmatches.\
                filter(CompletedMatch.competition_id == competition_id)
    else:
        cmatches = cmatches.\
                filter(CompletedMatch.competition_id.in_(competition_ids))

    cmatches = cmatches.all()

    total_wins = 0
    total_losses = 0
    total_draws = 0
    seen_matches = set()
    for c in cmatches:
        cmatch_id = c[0]
        if cmatch_id in seen_matches:
            continue
        seen_matches.add(cmatch_id)

        if c.wins > c.losses:
            total_wins += 1
        elif c.wins < c.losses:
            total_losses += 1
        else:
            total_draws += 1

    phash = dict()
    for p in team.players:
        phash[p.user_id] = p.user.name

    return rt('teams/stats.html',
            page=page,
            game=game,
            combined=True,
            total_stats=stats,
            stats=[],
            phash=phash,
            gametype=gametype,
            map=mapp,
            combine_form=combine_form,
            competition=competition,
            total_wins=total_wins,
            total_losses=total_losses,
            total_draws=total_draws,
            team=team)
