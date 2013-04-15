import datetime
import collections

from sqlalchemy.orm import eagerload, join, outerjoin
from sqlalchemy.orm.exc import NoResultFound

from flask import Module, g, request, flash, url_for
from flask_mail import Message
from flaskext.babel import to_user_timezone, to_utc

from tardyrush import db, mail

from tardyrush.helpers import rt, jsonify, abs_url_for, redirect
from tardyrush.helpers.teams import *
from tardyrush.helpers.consts import *
from tardyrush.helpers.filters import *
from tardyrush.views import require_login

from tardyrush.models import \
        Team, TeamPlayer, MatchPlayerStatusForm, Competition, \
        Opponent, OpponentForm, ServerForm, \
        MatchPlayer, Match, Server, MatchForm, AddMatchForm, \
        User, ForumBotQueuedPost, UserTimeZoneForm, CompletedMatch

matches = Module(__name__)

@matches.route('/match/add/', methods=('GET','POST'))
@require_login(page={'top':'my_matches','sub':'add_match'})
def add():
    if not g.user.is_team_leader():
        flash(u'You must be a team leader to add a match.', 'error')
        return redirect(url_for('my_matches'))

    opponents = Opponent.query.\
            filter(Opponent.team_id.in_(g.user.team_leader_teams)).\
            order_by(Opponent.name.asc()).all()

    servers = Server.query.\
            filter(Server.team_id.in_(g.user.team_leader_teams)).\
            order_by('server_name')
    competitions = Competition.query.order_by('competition_name')

    form = AddMatchForm()
    form.team_id.choices = [ (t, g.user.teams[t].name) for t in g.user.team_leader_teams ]
    form.competition_id.choices = [(c.id, c.name) for c in competitions ]
    form.server_id.choices = [ (s.id, s.name) for s in servers ]
    form.opponent_id.choices = [ (o.id, o.name) for o in opponents ]

    if request.method == 'GET':
        if request.values.get('new_opponent_id'):
            form.opponent_id.data = int(request.values.get('new_opponent_id'))
        elif request.values.get('new_server_id'):
            form.server_id.data = int(request.values.get('new_server_id'))

        # default to tomorrow at 9pm
        form.date.data = datetime.datetime.combine((\
                    to_user_timezone(datetime.datetime.utcnow()) \
                        + datetime.timedelta(days=1))\
                        .date(),\
                    datetime.time(21))
        form.date.label.text += ' (in %s)' \
                % format_datetime(form.date.data, 'zzzz')

    if form.validate_on_submit():
        if not g.user.is_team_leader(form.team_id.data):
            flash(u'You must be a team leader to add a match.', 'error')
        else:
            date = to_utc(form.date.data)
            match = Match(team_id=form.team_id.data,
                          date=date,
                          comments=form.comments.data,
                          password=form.password.data,
                          opponent_id=form.opponent_id.data,
                          competition_id=form.competition_id.data,
                          creator_user_id=g.user.id,
                          server_id=form.server_id.data)
            db.session.add(match)
            db.session.commit()

            team_date = matches_datetime_format_full_for_team(date, \
                    g.user.teams[form.team_id.data].time_zone)

            date_short = matches_datetime_format(date)
            team_date_short = matches_datetime_format_for_team(date, \
                    g.user.teams[form.team_id.data].time_zone)

            email_vars = { 'date' : matches_datetime_format_full(date),
                           'team_date' : team_date,
                           'date_short' : date_short,
                           'team_date_short' : team_date_short,
                           'team' : g.user.teams[form.team_id.data].name,
                           'opponent' : match.opponent.name,
                           'opponent_tag' : match.opponent.tag,
                           'competition' : match.competition.name,
                           'server' : match.server.name,
                           'address' : match.server.address,
                           'password' : match.password,
                           'comments' : match.comments,
                           'match_url' : abs_url_for('show',
                               match_id=match.id),
                           'settings_url' : abs_url_for('account.settings') }

            subject = "[tardyrush] New Match "\
                    "on %(date_short)s vs. %(opponent_tag)s" %\
                    email_vars
            team_subject = "[tardyrush] New Match "\
                    "on %(team_date_short)s vs. %(opponent_tag)s" %\
                    email_vars

            lines = [ "A new match has been added." ]
            lines.append("")

            lines.append( "%(team)s vs. %(opponent)s" % email_vars )
            lines.append( "%%(date)s" % email_vars )
            lines.append("")

            lines.append( "Competition: %(competition)s" % email_vars )
            lines.append( "Server: %(server)s" % email_vars )
            lines.append( "Address: %(address)s" % email_vars )
            if len(email_vars['password']):
                lines.append( "Password: %(password)s" % email_vars )
            lines.append("")

            if len(email_vars['comments']):
                lines.append( "Comments:" )
                lines.append( "%(comments)s" % email_vars )
                lines.append("")

            lines.append( "Set your status: %(match_url)s" % email_vars )
            lines.append("")

            lines.append( "Change your settings: %(settings_url)s" % email_vars )
            lines.append("")

            raw_message = "\n".join(lines)

            message = raw_message % email_vars
            team_message = raw_message % { 'date' : email_vars['team_date'] }

            # now notify players of new match via email
            players = db.session.query(User).\
                    select_from(join(User, TeamPlayer)).\
                    filter(TeamPlayer.team_id==form.team_id.data).\
                    filter(User.email_settings==User.EmailMatchAdded)

            if form.send_notification.data:
                try:
                    with mail.connect() as conn:
                        for p in players:
                            try:
                                msg = Message(recipients=[p.email],
                                              body=message,
                                              subject=subject,
                                              sender=Sender)
                                conn.send(msg)
                                app.logger.info("Sent mail to: %s" % p.email)
                            except Exception, e:
                                app.logger.error("Error sending mail: %s, %s" % \
                                        (p.email, e))
                except Exception, e:
                    app.logger.error("Error sending mail: %s" % e)

            # now notify players of new match via forum post
            if form.post_on_forums.data:
                forum_post = ForumBotQueuedPost(team_id=match.team_id,
                                                game_id=match.competition.game_id,
                                                match_id=match.id,
                                                subject=team_subject,
                                                message=team_message)
                db.session.add(forum_post)
                db.session.commit()

            flash(u'The match was successfully added.', 'success')
            return redirect(url_for('my_matches'))

    oform = OpponentForm()
    sform = ServerForm()
    tzform = UserTimeZoneForm(obj=g.user)

    return rt('matches/form.html',
            page={'top':'my_matches', 'sub':'add_match'},
            adding=True,
            team_id=g.user.team_leader_teams[0],
            user_now=to_user_timezone(datetime.datetime.utcnow()),
            tzform=tzform,
            oform=oform,
            sform=sform,
            form=form)

@matches.route('/match/<int:match_id>/', defaults={'action':''})
@matches.route('/match/<int:match_id>/<action>/', methods=('GET','POST'))
@require_login()
def show(match_id, action):
    match = Match.query.filter_by(id=match_id).first()
    if not match:
        flash(u"That match doesn't exist.", "error")
        return redirect(url_for('my_matches'))

    if not g.user.is_on_team(match.team_id):
        flash(u'You must be on the team to view its match availability.', "error")
        return redirect(url_for('all'))

    if match.date < datetime.datetime.utcnow():
        up_prev = 'previous'
    else:
        up_prev = 'upcoming'

    if action == 'edit':
        if not g.user.is_team_leader(match.team_id):
            flash(u'You must be a team leader to edit this match.', 'error')
            return redirect(url_for('my_matches'))

        servers = Server.query.\
                filter_by(team_id=match.team_id).\
                order_by('server_name')

        form = MatchForm(request.form, obj=match)
        form.competition_id.choices = [(c.id, c.name) for c in
                Competition.query.order_by('competition_name')]
        form.server_id.choices = [ (s.id, s.name) for s in servers ]
        form.team_id.choices = [ (t, g.user.teams[t].name) for t in g.user.team_leader_teams ]
        form.opponent_id.choices = [ (o.id, o.name) for o in \
                Opponent.query.filter_by(team_id=match.team_id).\
                order_by(Opponent.name.asc()).all() ]

        players = {}
        for p in match.players:
            players[p.user_id] = p.user.name

        if request.method == 'GET':
            if request.values.get('new_opponent_id'):
                form.opponent_id.data = int(request.values.get('new_opponent_id'))
            elif request.values.get('new_server_id'):
                form.server_id.data = int(request.values.get('new_server_id'))

            form.date.data = to_user_timezone(form.date.data)
            form.date.label.text += ' (in %s)' \
                    % format_datetime(form.date.data, 'zzzz')

        if form.validate_on_submit():
            form.date.data = to_utc(form.date.data)

            to_delete = []
            for f in form.players:
                if f.delete.data:
                    to_delete.append(f.user_id.data)

            form.populate_obj(match)

            if len(to_delete):
                MatchPlayer.query.\
                        filter_by(match_id=match_id).\
                        filter(MatchPlayer.user_id.in_(to_delete)).delete(False)

            db.session.commit()
            flash(u'The match was successfully updated.', 'success')

            if request.values.get('from') == 'single':
                return redirect(url_for('show', match_id=match_id))

            return redirect(url_for('my_matches'))

        oform = OpponentForm()
        sform = ServerForm()
        tzform = UserTimeZoneForm(obj=g.user)

        return rt('matches/form.html', form=form, players=players,
                page={'top':'my_matches', 'sub':up_prev},
                when=up_prev,
                adding=False,
                user_now=to_user_timezone(datetime.datetime.utcnow()),
                tzform=tzform,
                oform=oform,
                sform=sform,
                team_id=g.user.team_leader_teams[0],
                match_id=match.id)
    elif action == 'delete':
        if not g.user.is_team_leader(match.team_id):
            flash(u'You must be a team leader to edit this match.', 'error')
            return redirect(url_for('my_matches'))

        if request.method == 'POST':
            db.session.delete(match)
            db.session.commit()
            flash(u'The match was successfully deleted.', 'success')

        return redirect(url_for('my_matches'))
    elif action == 'status':
        if not g.user.is_on_team(match.team_id):
            flash(u'You must be on this team to change your status.', 'error')
            return redirect(url_for('my_matches'))

        if up_prev == 'previous':
            flash(u'You cannot change your status on a past match.', 'error')
            return redirect(url_for('my_previous_matches'))

        form = MatchPlayerStatusForm(request.form)

        if form.validate_on_submit():
            if request.values.get('s') == 'available':
                player_status = MatchPlayer.StatusAvailable
            elif request.values.get('s') == 'maybe':
                player_status = MatchPlayer.StatusMaybe
            elif request.values.get('s') == 'unavailable':
                player_status = MatchPlayer.StatusUnavailable
            else:
                player_status = None

            if player_status is None:
                flash(u'That status is not valid!', 'error')
            else:
                try:
                    mu = MatchPlayer.query.filter_by(match_id=match.id,
                                                     user_id=g.user.id).one()
                    mu.status = player_status
                except NoResultFound:
                    mu = MatchPlayer(match_id=match.id, user_id=g.user.id,
                                     status=player_status)
                except Exception, e:
                    app.logger.error('Error finding MatchPlayer: %s, %s' % \
                            (g.user.id, e))
                    flash(u'Something bad happened. Please try again.', 'error')
                    return redirect(url_for('my_matches'))

                mu.date_updated = datetime.datetime.utcnow()
                db.session.add(mu)
                db.session.commit()

                if request.values.get('api') == '1':
                    psp = mu.pretty_status
                    return jsonify(success=True,
                            csrf=form.csrf_token.data,
                            match_id=match.id,
                            user_id=g.user.id,
                            user_name=g.user.name,
                            player_status=player_status,
                            player_status_pretty=psp)

                if request.values.get('from') == 'single':
                    return redirect(url_for('show', match_id=match_id))
    else:
        return rt('matches/single.html',
                page={'top':'my_matches','sub':up_prev},
                when=up_prev,
                aform = MatchPlayerStatusForm(),
                match=match)

    return redirect(url_for('my_matches'))


###############
@matches.route('/match/')
@matches.route('/match/upcoming/')
def my_matches():
    if not g.user:
        return redirect(url_for('all'))

    cutoff = datetime.datetime.utcnow() - datetime.timedelta(hours=1)
    matches = Match.query.\
            outerjoin(CompletedMatch).\
            filter(CompletedMatch.id == None).\
            filter(Match.team_id.in_(g.user.teams.keys())).\
            filter(Match.date > cutoff).\
            options(eagerload('competition'), \
                    eagerload('server')).\
            order_by(Match.date.asc()).\
            order_by(Match.id.asc()).\
            all()

    return rt('matches/availability.html',
        page={'top':'my_matches', 'sub':'upcoming'},
        aform = MatchPlayerStatusForm(),
        matches=matches)

@matches.route('/match/previous/')
def my_previous_matches():
    if not g.user:
        return redirect(url_for('all'))

    cutoff = datetime.datetime.utcnow()
    matches = Match.query.\
            filter(Match.team_id.in_(g.user.teams.keys())).\
            filter(Match.date <= cutoff).\
            options(eagerload('competition'), \
                    eagerload('server')).\
            order_by(Match.date.asc()).\
            order_by(Match.id.asc()).\
            all()

    return rt('matches/table.html',
        page={'top':'my_matches', 'sub':'previous'},
        previous_only=True,
        previous=matches)

@matches.route('/match/all/')
def all(team_id=0): # show all matches
    team = None
    if team_id:
        if not g.user.is_on_team(team_id):
            team = Team.query.filter_by(id=team_id).first()

            if not team:
                return redirect(url_for('all'))

            page = {'top':'team', 'sub':'matches'}
        else:
            team = {'id' : team_id, 'name' : g.user.teams[team_id].name}
            page = {'top':'my_teams', 'sub':'matches'}

        matches=Match.query.\
                options(eagerload('competition')).\
                filter_by(team_id=team_id).\
                order_by(Match.date.asc()).\
                order_by(Match.id.asc()).\
                all()
    else:
        matches=Match.query.\
                options(eagerload('competition')).\
                order_by(Match.date.asc()).\
                order_by(Match.id.asc()).\
                all()
        page={'top':'matches', 'sub':'all_matches'}

    now = datetime.datetime.utcnow()
    upcoming = []
    previous = []
    for m in matches:
        if m.date > now:
            upcoming.append(m)
        else:
            previous.append(m)

    return rt('matches/table.html',
        page=page, team=team,
        upcoming=upcoming, previous=previous)

