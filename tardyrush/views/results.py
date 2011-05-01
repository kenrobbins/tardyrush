import collections
import datetime

from flask import Module, g, session, request, flash, url_for
from flaskext.babel import refresh as babel_refresh
from flaskext.babel import to_utc, to_user_timezone

from tardyrush import oid, app, db
from tardyrush.views import require_login
from tardyrush.helpers import rt, jsonify, abs_url_for, redirect
from tardyrush.helpers.filters import *
from tardyrush.helpers.teams import *
from tardyrush.models import \
        CompletedMatch, Match, Opponent, Server, Map, Side, GameType, \
        Team, CompletedMatchRound, CompletedMatchPlayer, CompletedMatchForm

results = Module(__name__)

@results.route('/results/add/', defaults={'cmatch_id':0,'action':''}, \
                            methods=('GET','POST'))
@results.route('/results/<int:cmatch_id>/<action>/', methods=('GET','POST'))
@require_login(page={'top':'my_matches','sub':'previous'})
def add(cmatch_id, action):
    if not is_team_leader():
        flash(u'You must be a team leader to add results.')
        return redirect(url_for('matches.my_matches'))

    if cmatch_id > 0:
        corr_match_id = cmatch_id
        adding = False

        corr_match = CompletedMatch.query.filter_by(id=cmatch_id).first()
        if not corr_match:
            flash(u'Results not found.')
            return redirect(url_for('matches.my_matches'))
    else:
        cmatch_id = 0
        adding = True
        corr_match_id = request.values.get('match_id')
        corr_match = Match.query.filter_by(id=corr_match_id).\
                filter(Match.team_id.in_(g.team_leader_teams)).first()

        if not corr_match:
            flash(u'Corresponding availability match not found.')
            return redirect(url_for('matches.my_matches'))

        if corr_match.date > datetime.datetime.utcnow():
            flash(u'Cannot add results to match in the future.')
            return redirect(url_for('matches.my_matches'))

        if len(corr_match.results):
            flash(u'Results have already been added.')
            return redirect(url_for('add',
                cmatch_id=corr_match.results[0].id,
                action='edit'))

    opponents = Opponent.query.\
            filter(Opponent.team_id.in_(g.team_leader_teams)).\
            order_by(Opponent.name.asc()).all()

    servers = Server.query.\
            filter(Server.team_id.in_(g.team_leader_teams)).\
            order_by('server_name')

    if not adding:
        form = CompletedMatchForm(request.form, obj=corr_match)
        if request.method == 'GET':
            form.date_played.data = to_user_timezone(corr_match.date_played)
    else:
        form = CompletedMatchForm()
        if request.method == 'GET':
            form.date_played.data = to_user_timezone(corr_match.date)

    form.match_id.data = int(corr_match_id)
    form.team_id.choices = [ (corr_match.team_id, g.teams[corr_match.team_id]) ]
    form.competition_id.choices = [ (corr_match.competition.id,
        corr_match.competition.name) ]
    form.server_id.choices = [ (corr_match.server.id,
        corr_match.server.name) ]
    form.opponent_id.choices = [ (corr_match.opponent.id,
        corr_match.opponent.name) ]

    form.team_id.data = corr_match.team_id
    form.competition_id.data = corr_match.competition_id
    form.server_id.data = corr_match.server_id
    form.opponent_id.data = corr_match.opponent_id

    #cutoff = datetime.datetime.utcnow() + datetime.timedelta(hours=2)
    #recent_matches = Match.query.\
    #        filter(Match.team_id.in_(g.team_leader_teams)).\
    #        filter(Match.date < cutoff).\
    #        order_by(Match.date.desc()).all()

    #form.match_id.choices = [ (m.id, "%s vs %s" % (m.date,
    #    m.opponent.tag)) for m in recent_matches ]

    maps = Map.query.filter_by(game_id=corr_match.competition.game_id).\
                     order_by(Map.name.asc()).all()
    map_choices = [ (m.id, m.name) for m in maps ]

    sides = Side.query.filter_by(game_id=corr_match.competition.game_id).\
                       order_by(Side.name.asc()).all()
    side_choices = [ (s.id, s.name) for s in sides ]

    gametypes = GameType.query.\
            filter_by(game_id=corr_match.competition.game_id).\
            order_by(GameType.name.asc()).\
            all()
    gametype_choices = [ (gt.id, gt.name) for gt in gametypes ]

    players = Team.query.filter_by(id=corr_match.team_id).first().\
            players.all()
    player_choices = \
            sorted([ (p.user_id, p.user.name) for p in players ],
                   key=lambda x: x[1].lower())

    if adding and request.method == 'GET':
        form.rounds.append_entry()
        form.rounds.append_entry()

    for e in form.rounds.entries:
        e.map_id.choices = map_choices
        e.side_id.choices = side_choices
        e.gametype_id.choices = gametype_choices

        if adding and request.method == 'GET':
            e.players.append_entry()
            e.players.append_entry()
            e.players.append_entry()
            e.players.append_entry()

        for ep in e.players.entries:
            ep.user_id.choices = player_choices

    if form.validate_on_submit():
        if not is_team_leader(form.team_id.data):
            flash(u'Invalid team')
        elif not len(form.rounds):
            flash(u'Invalid rounds')
        else:
            error = False

            date = to_utc(form.date_played.data)
            if adding:
                cmatch = CompletedMatch(team_id=form.team_id.data,
                                        date_created=datetime.datetime.utcnow(),
                                        opponent_id=form.opponent_id.data,
                                        competition_id=form.competition_id.data,
                                        creator_user_id=g.user.id,
                                        server_id=form.server_id.data,
                                        match_id=corr_match.id)
            else:
                cmatch = corr_match
                for r in cmatch.rounds.all():
                    cmatch.rounds.remove(r)

            cmatch.date_played = date
            cmatch.comments = form.comments.data

            if request.values.get('forfeit_result') in ('1', '0'):
                cmatch.final_result_method = CompletedMatch.FinalResultByForfeit
                cmatch.draws = 0

                if request.values.get('forfeit_result') == '1':
                    cmatch.wins = 1
                    cmatch.losses = 0
                else:
                    cmatch.wins = 0
                    cmatch.losses = 1

                if adding:
                    db.session.add(cmatch)

                db.session.commit()

                flash(u'The results were successfully saved.')
                return redirect(url_for('matches.my_previous_matches'))

            else:
                cmatch.final_result_method = form.final_result_method.data
                cmatch.wins = 0
                cmatch.losses = 0
                cmatch.draws = 0

            if adding:
                db.session.add(cmatch)
                db.session.flush()

            total_wins = 0
            total_losses = 0
            total_draws = 0
            round_wins = 0
            round_losses = 0
            round_draws = 0

            round_num = 1
            for r in form.rounds:
                rnd = CompletedMatchRound(cmatch_id=cmatch.id,
                                          round_id=round_num,
                                          map_id=r.map_id.data,
                                          side_id=r.side_id.data,
                                          gametype_id=r.gametype_id.data,
                                          wins=r.wins.data,
                                          losses=r.losses.data,
                                          draws=r.draws.data)
                cmatch.rounds.append(rnd)
                db.session.flush()

                if not len(r.players):
                    flash(u'No players found')
                    error = True
                    break

                total_wins += rnd.wins
                total_losses += rnd.losses
                total_draws += rnd.draws

                if rnd.wins > rnd.losses:
                    round_wins += 1
                elif rnd.wins < rnd.losses:
                    round_losses += 1
                else:
                    round_draws += 1

                player_set = set()
                for p in r.players:
                    if p.user_id.data in player_set:
                        errmsg = u'You have duplicate players in round %d. ' %\
                                round_num
                        errmsg += 'A player may appear in a round only once.'
                        flash(errmsg)
                        error = True
                        break

                    player_set.add(p.user_id.data)
                    player = CompletedMatchPlayer(cmatch_id=cmatch.id,
                                                  round_id=round_num,
                                                  user_id=p.user_id.data,
                                                  kills=p.kills.data,
                                                  deaths=p.deaths.data,
                                                  off_objs=p.off_objs.data,
                                                  def_objs=p.def_objs.data)
                    rnd.players.append(player)

                if error:
                    break

                round_num += 1

            if cmatch.final_result_method == CompletedMatch.FinalResultByScore:
                cmatch.wins = total_wins
                cmatch.losses = total_losses
                cmatch.draws = total_draws
            else:
                cmatch.wins = round_wins
                cmatch.losses = round_losses
                cmatch.draws = round_draws

            if error:
                db.session.rollback()
            else:
                db.session.commit()

                flash(u'The results were successfully saved.')
                return redirect(url_for('matches.my_previous_matches'))

    return rt('completed_matches/new.html', 
            page={'top':'my_matches', 'sub':'previous'},
            adding=adding,
            player_choices=player_choices,
            map_choices=map_choices,
            side_choices=side_choices,
            gametype_choices=gametype_choices,
            form=form)

@results.route('/results/<int:cmatch_id>/')
def show(cmatch_id):
    cmatch = CompletedMatch.query.filter_by(id=cmatch_id).first()
    if not cmatch:
        flash(u'Match not found')
        return redirect('show_all')

    if cmatch.team_id in g.teams:
        page={'top':'my_matches','sub':'previous'}
    else:
        page={'top':'matches','sub':'previous'}

    players = dict()
    kills = collections.defaultdict(int)
    deaths = collections.defaultdict(int)
    off_objs = collections.defaultdict(int)
    def_objs = collections.defaultdict(int)
    for r in cmatch.rounds:
        for p in r.players:
            kills[p.user_id] += p.kills
            deaths[p.user_id] += p.deaths
            players[p.user_id] = p.user.name
            off_objs[p.user_id] += p.off_objs
            def_objs[p.user_id] += p.def_objs

    return rt('completed_matches/match.html', 
            page=page,
            players=players,
            kills=kills,
            deaths=deaths,
            off_objs=off_objs,
            def_objs=def_objs,
            cmatch=cmatch)

