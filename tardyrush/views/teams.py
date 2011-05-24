import datetime
import collections

from flask import Module, g, flash, url_for, request
from tardyrush import db
from tardyrush.views import require_login
from tardyrush.helpers import rt, jsonify, abs_url_for, redirect
from tardyrush.helpers.filters import *
from tardyrush.helpers.teams import is_founder, is_team_leader, \
        is_on_current_team
from tardyrush.models import \
        Team, TeamForm, TeamPlayersForm, LeaveTeamForm, JoinTeamForm, \
        CompletedMatch, CompletedMatchPlayer, CompletedMatchRound, \
        MatchPlayer, Match, GameType, \
        User, TeamPlayer
from matches import all as matches_all

teams = Module(__name__)

@teams.route('/team/all/')
@teams.route('/teams/all/')
def all():
    return rt('teams/table.html',
            page={'top':'teams', 'sub':'all_teams'},
            all_teams=True,
            teams=Team.query.order_by(Team.name.asc()).all())

# show teams the current user is on
@teams.route('/team/')
@teams.route('/my_teams/')
@teams.route('/teams/')
def my_teams():
    if len(g.teams):
        return show()

    return redirect(url_for('all'))

@teams.route('/team/<action>/', defaults={'team_id':-1}, methods=('GET','POST'))
@teams.route('/team/<int:team_id>/', defaults={'action':''})
@teams.route('/team/<int:team_id>/<action>/', methods=('GET','POST'))
def show(team_id=-1, action=''):
    page = { 'top' : 'team', 'sub' : 'main' }

    if team_id and type(team_id) == int:
        if team_id == -1 and len(g.teams) == 1:
            team_id = g.teams.keys()[0]
            page = {'top':'my_teams', 'sub':'all_my'}
        elif team_id in g.teams:
            page = {'top':'my_teams', 'sub':'all_my'}
 
        if team_id == -1:
            if g.user:
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
            flash(u'Team not found')
            return redirect(url_for('all'))

        if action == 'join':
            if not g.user:
                flash(u'You must be signed in to join a team.')
            elif is_on_current_team(team_id):
                flash(u'You are already on this team.')
            elif len(g.teams): # TODO support for more than 1 team
                flash(u'You are already on a team.  Leave your current team '
                       'first before joining this team.')
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
                    flash(u'You have successfully joined this team.')

                return redirect(url_for('show', team_id=team.id))

        elif action == 'leave':
            if not g.user:
                flash(u'You must be signed in to join a team.')
            elif not is_on_current_team(team_id):
                flash(u'You are not on this team.')
            else:
                leave_form = LeaveTeamForm(request.form)

                if leave_form.validate_on_submit():
                    # make sure there is still a founder on the team

                    skip = False
                    if team.id in g.founder_teams:
                        other_founders = False
                        for p in team.players:
                            if p.status == TeamPlayer.StatusFounder and \
                                    p.user_id != g.user.id:
                                other_founders = True
                                break

                        if not other_founders:
                            flash(u'''You cannot leave this team because you are
                                the only founder.  Add another founder
                                first.''')
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
                        flash(u'You have successfully left this team.')
                        return redirect(url_for('show',team_id=team.id))

        # only edit or delete for own team if a team leader
        elif is_team_leader(team_id):
            if action == 'edit' and \
                    request.values.get('edit_players') == '1':
                action = 'edit_players'

            team_names = [ t.name.lower() for t in Team.query.all() ]
            if team.name.lower() in team_names:
                team_names.remove(team.name.lower())

            form = TeamForm(request.form, obj=team, no_formdata = (action != 'edit'))
            form.name.validators[0].values = team_names

            players_form = TeamPlayersForm(request.form, obj=team,
                    no_formdata=(action != 'edit_players'))

            if action == 'edit':
                players = {}
                for p in team.players:
                    players[p.user_id] = p.user.name

                if not is_founder(team_id):
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
                    flash(u'Team was successfully updated')
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

                if not is_founder(team_id):
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
                        flash(u'There must be at least one founder on the team.')
                        save = False

                    if team_id not in g.founder_teams and \
                            (editing_founders or deleting_founders):
                        flash(u'You must be a founder to edit or delete a '
                               'founder.')
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
                        flash(u'Team was successfully updated')
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
                    flash(u'Team was successfuly deleted')
                    return redirect(url_for('all'))

                flash(u'Team not found')
                return redirect(url_for('show', team_id=team.id))

        elif action in ('delete', 'edit'):
            flash(u'You must be a team leader to edit the team.')

        join_form = None
        leave_form = None
        if g.user:
            if team_id not in g.teams:
                join_form = JoinTeamForm()
            else:
                leave_form = LeaveTeamForm()

        cmatches = CompletedMatch.query.filter_by(team_id=team_id).all()

        # TODO: do this in sql
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
    if len(g.teams):
        flash(u'You are already on a team.  Leave your current team first '
               'before creating a new one.')
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

        flash(u'The team was successfully created.')
        return redirect(url_for('matches.my_matches'))

    return rt('teams/create.html', 
            page={'top': 'teams', 'sub': 'add_team'},
            adding=True,
            form=form)

@teams.route('/team/<int:team_id>/matches/')
@teams.route('/teams/<int:team_id>/matches/')
def matches(team_id=0):
    return matches_all(team_id)

@teams.route('/team/<int:team_id>/records/')
@teams.route('/teams/<int:team_id>/records/')
def records(team_id=0):
    api = request.values.get('api') == '1'

    team = Team.query.filter_by(id=team_id).first()

    if not team:
        return redirect(url_for('all'))

    match_id = request.values.get('match_id')
    match = Match.query.filter_by(id=match_id).first()

    if not match:
        return redirect(url_for('all'))

    ( opponent_rec, competition_rec, server_rec, opp_comp_rec ) = \
            match.get_match_records(team_id)

    return jsonify(success=True, opponent_rec=opponent_rec,
            competition_rec=competition_rec, server_rec=server_rec, 
            opp_comp_rec=opp_comp_rec)

@teams.route('/team/<int:team_id>/stats/')
@teams.route('/teams/<int:team_id>/stats/')
def stats(team_id=0):
    team = Team.query.filter_by(id=team_id).first()

    if not team:
        return redirect(url_for('all'))

    if team_id in g.teams:
        page = { 'top' : 'my_teams', 'sub' : 'player_stats' }
    else:
        page = { 'top' : 'team', 'sub' : 'player_stats' }

    ##########################################################
    # fetch totals

    pcount_subquery = \
            db.session.query(CompletedMatchPlayer.user_id).\
            join((CompletedMatch,
                  CompletedMatchPlayer.cmatch_id == CompletedMatch.id)).\
            filter(CompletedMatch.team_id == team_id).\
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
                         group_by(record_subquery.c.user_id)

    stats_pm = dict()
    for s in records:
        stats_pm[ s[0] ] = (s[1], s[2])

    stats_res = db.session.query(CompletedMatchPlayer.user_id,
                                 db.func.sum(CompletedMatchPlayer.kills),
                                 db.func.sum(CompletedMatchPlayer.deaths),
                                 db.func.sum(CompletedMatchPlayer.off_objs),
                                 db.func.sum(CompletedMatchPlayer.def_objs),
                  db.func.count(db.func.distinct(CompletedMatch.id))).\
            join((CompletedMatch, 
                  CompletedMatchPlayer.cmatch_id == CompletedMatch.id)).\
            filter(CompletedMatch.team_id == team_id).\
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
        stats_item = { 'user_id' : s[0],
                       'kills' : s[1],
                       'deaths' : s[2],
                       'offobjs' : s[3],
                       'defobjs' : s[4],
                       'wins' : w,
                       'losses' : l,
                       'pos_kdr' : pos_kdr
                     }
        total_stats.append(stats_item)

    ##########################################################

    pcount_subquery = \
            db.session.query(CompletedMatchPlayer.user_id,
                             CompletedMatchRound.gametype_id).\
            join((CompletedMatch,
                  CompletedMatchPlayer.cmatch_id == CompletedMatch.id)).\
            join((CompletedMatchRound,\
                  db.and_(\
                      CompletedMatchRound.cmatch_id == CompletedMatch.id,\
                      CompletedMatchRound.round_id ==\
                          CompletedMatchPlayer.round_id,\
                  ))).\
            filter(CompletedMatch.team_id == team_id).\
            group_by(CompletedMatchRound.gametype_id).\
            group_by(CompletedMatchPlayer.cmatch_id).\
            group_by(CompletedMatchPlayer.user_id).\
            having(db.func.sum(CompletedMatchPlayer.kills) >=\
                   db.func.sum(CompletedMatchPlayer.deaths)).\
            with_entities(CompletedMatchPlayer.user_id,\
                          CompletedMatchRound.gametype_id).\
            subquery()

    positive_counts = db.engine.execute( \
            db.select(columns=['user_id', 'gametype_id', db.func.count()],\
                      from_obj=pcount_subquery).\
            group_by('gametype_id', 'user_id') )
   
    pcounts = dict()
    for p in positive_counts:
        pcounts[ (p[0], p[1]) ] = p[2]

    record_subquery = \
            db.session.query(CompletedMatchPlayer.user_id,
                             CompletedMatchRound.gametype_id,
                             CompletedMatchPlayer.cmatch_id).\
            join((CompletedMatchRound,\
                  db.and_(\
                      CompletedMatchRound.cmatch_id ==\
                          CompletedMatchPlayer.cmatch_id,\
                      CompletedMatchRound.round_id ==\
                          CompletedMatchPlayer.round_id,\
                  ))).\
            group_by(CompletedMatchRound.gametype_id).\
            group_by(CompletedMatchPlayer.cmatch_id).\
            group_by(CompletedMatchPlayer.user_id).\
            with_entities(CompletedMatchPlayer.user_id,\
                          CompletedMatchRound.gametype_id,
                          CompletedMatchPlayer.cmatch_id).\
            subquery()

    records = db.session.query(\
            record_subquery.c.user_id,
                               record_subquery.c.gametype_id,
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
                         group_by(record_subquery.c.gametype_id).\
                         group_by(record_subquery.c.user_id)

    stats_pm = dict()
    for s in records:
        stats_pm[ (s[0], s[1]) ] = (s[2], s[3])

    stats_res = db.session.query(CompletedMatchPlayer.user_id,
                                 CompletedMatchRound.gametype_id,
                                 db.func.sum(CompletedMatchPlayer.kills),
                                 db.func.sum(CompletedMatchPlayer.deaths),
                                 db.func.sum(CompletedMatchPlayer.off_objs),
                                 db.func.sum(CompletedMatchPlayer.def_objs),
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
            group_by(CompletedMatchRound.gametype_id).\
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
        stats_item = { 'user_id' : s[0],
                       'gametype_id' : s[1],
                       'kills' : s[2],
                       'deaths' : s[3],
                       'offobjs' : s[4],
                       'defobjs' : s[5],
                       'wins' : w,
                       'losses' : l,
                       'pos_kdr' : pos_kdr
                     }
        stats.append(stats_item)

    cmatches = db.session.query(CompletedMatchRound.gametype_id,
            CompletedMatchRound.cmatch_id,
            CompletedMatch.wins, CompletedMatch.losses).\
            join(CompletedMatch).\
            filter_by(team_id=team_id).all()

    # TODO: do this in sql
    total_wins = 0
    total_losses = 0
    total_draws = 0
    seen_matches = set()
    wins = collections.defaultdict(int)
    losses = collections.defaultdict(int)
    draws = collections.defaultdict(int)
    for c in cmatches:
        if (c.cmatch_id, c.gametype_id) in seen_matches:
            continue
        seen_matches.add((c.cmatch_id, c.gametype_id))
        wins[c.gametype_id] += 0
        if c.wins > c.losses:
            wins[c.gametype_id] += 1
            total_wins += 1
        elif c.wins < c.losses:
            losses[c.gametype_id] += 1
            total_losses += 1
        else:
            draws[c.gametype_id] += 1
            total_draws += 1

    gametypes = GameType.query.all()
    gthash = dict()
    for gt in gametypes:
        gthash[gt.id] = gt.name

    phash = dict()
    for p in team.players:
        phash[p.user_id] = p.user.name

    return rt('teams/stats.html', 
            page=page,
            stats=stats,
            stats_pm=stats_pm,
            pcounts=pcounts,
            gthash=gthash,
            phash=phash,
            wins=wins, losses=losses, draws=draws,
            total_stats=total_stats,
            total_wins=total_wins, total_losses=total_losses,
            total_draws=total_draws,
            team=team)

