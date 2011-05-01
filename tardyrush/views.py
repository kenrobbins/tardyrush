from __future__ import with_statement

from tardyrush import app
from flask import request, flash, url_for, render_template, \
        abort, g, session, get_flashed_messages
from flask import redirect as flask_redirect
from flask import jsonify as flask_jsonify

from models import *
from sqlalchemy.orm import eagerload, join
from sqlalchemy.orm.exc import NoResultFound

import datetime
import collections

import urllib

from flaskext.wtf import ValidationError

from flaskext.openid import OpenID
oid = OpenID(app)

from flaskext.babel import Babel, format_datetime, to_user_timezone, to_utc
from flaskext.babel import refresh as babel_refresh
babel = Babel(app)

import pytz

from flaskext.mail import Mail, Message
mail = Mail(app)

from collections import defaultdict
from babel import dates

def abs_url_for(*args, **kwargs):
    return "http://tardyrush.com%s" % url_for(*args, **kwargs)

Sender = ("tardyrush", "tardyrush@tardyrush.com")

@babel.timezoneselector
def get_timezone():
    if g.user and g.user.time_zone in pytz.common_timezones:
        return g.user.time_zone
    return 'US/Eastern' # this is the default time zone when not logged in

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

def jsonify(*args, **kwargs):
    kwargs.setdefault('flashes', get_flashed_messages(with_categories=True))
    return flask_jsonify(*args, **kwargs)

def rt(*args, **kwargs):
    if request.values.get('api') == '1':
        if 'form' in kwargs and kwargs['form']:
            errors = kwargs['form'].errors
        else:
            errors = []
        return jsonify(success=False, errors=errors)
    kwargs.setdefault('page', {'top':'main', 'sub':''})
    return render_template(*args, **kwargs)

def redirect(*args, **kwargs):
    if request.values.get('api') == '1':
        return jsonify(success=False)
    return flask_redirect(*args, **kwargs)

import re

from jinja2 import evalcontextfilter, Markup, escape

_paragraph_re = re.compile(r'(?:\r\n|\r|\n){2,}')

@app.template_filter('nl2br')
@evalcontextfilter
def nl2br(eval_ctx, value):
    result = u'\n\n'.join(u'<p>%s</p>' % p.replace('\n', '<br/>\n') \
        for p in _paragraph_re.split(escape(value)))
    if eval_ctx.autoescape:
        result = Markup(result)
    return result

@app.template_filter()
def urlencode(url, **kwargs):
    seq = []
    for key, val in kwargs.iteritems():
        if isinstance(val, (list, tuple)):
            for v in val:
                seq.append( (key, v) )
        else:
            seq.append( (key, val) )
    return "%s?%s" % (url, urllib.urlencode(seq))

@app.template_filter()
def urlquote(s, safe=''):
    return urllib.quote(s, safe)

@app.template_filter()
def is_forfeit(val):
    return val == CompletedMatch.FinalResultByForfeit

@app.template_filter()
def server_copy_text(fmt, m):
    fmt = fmt.replace("%ADDR%", m.server.address)
    fmt = fmt.replace("%PW%", m.password)
    return fmt

@app.template_filter()
def add_time(dt, **kwargs):
    return dt + datetime.timedelta(**kwargs)

@app.template_filter()
def kdr(fmt, kills, deaths):
    if deaths == 0:
        return '<span class="inf_kdr">&#8734;</span>'
    kdr = float(kills) / float(deaths)
    return fmt % kdr

@app.template_filter()
def pretty_forum_bot_type(value):
    return ForumBot.TypePrettyNames[value] 

@app.template_filter()
def pretty_team_player_status(value):
    return TeamPlayer.StatusPrettyNames[value] 

@app.template_filter()
def pretty_match_player_status(value):
    return MatchPlayer.StatusPrettyNames[value] 

@app.template_filter()
def can_edit_match(team_id=None):
    return is_team_leader(team_id)

@app.template_filter()
def can_edit_team(team_id=None):
    return is_team_leader(team_id)

@app.template_filter()
def user_time_zone(fmt=None):
    if not fmt:
        fmt = 'zzzz'
    return format_datetime(to_user_timezone(datetime.datetime.utcnow()),
            fmt)

@app.template_filter()
def match_last_updated_format(value):
    return format_datetime(value, "MMM d 'at' h':'mm a")

@app.template_filter()
def matches_datetime_format(value):
    # show the year if the value's year is not the current year, but only do
    # that if it's more than 45 days in the future.  that way, at end of the
    # year, it doesn't show the year for everything.
    utcnow = datetime.datetime.utcnow()
    if value.year != utcnow.year:
        return format_datetime(value, "MMM d',' yyyy 'at' h':'mm a zzz")

    return format_datetime(value, "EEE',' MMM d 'at' h':'mm a zzz")

def matches_datetime_format_for_team(value, tz):
    utcnow = datetime.datetime.utcnow()
    if value.year != utcnow.year:
        return dates.format_datetime(value,
                "MMM d',' yyyy 'at' h':'mm a zzz",
                locale='en_US',
                tzinfo=pytz.timezone(tz))

    return dates.format_datetime(value,
            "EEE',' MMM d 'at' h':'mm a zzz",
            locale='en_US',
            tzinfo=pytz.timezone(tz))

@app.template_filter()
def matches_date_format(value):
    return format_datetime(value, "MMMM d',' yyyy")

@app.template_filter()
def matches_time_format(value):
    return format_datetime(value, "h':'mm a zzz")

@app.template_filter()
def matches_datetime_format_full(value):
    return format_datetime(value, "EEEE',' MMMM d',' yyyy 'at' h':'mm a zzz")

def matches_datetime_format_full_for_team(dt, tz):
    return dates.format_datetime(dt,
            "EEEE',' MMMM d',' yyyy 'at' h':'mm a zzz",
            locale='en_US',
            tzinfo=pytz.timezone(tz))

@app.before_request
def lookup_current_user():
    g.user = None
    if 'openid' in session:
        g.user = User.query.filter_by(openid=session['openid']).first()
    elif app.debug and 'force_login' in session:
        g.user = User.query.filter_by(name=session['force_login']).first()

    g.team_leader_teams = []
    g.founder_teams = []
    g.teams = {}
    g.teams_time_zones = {}
    g.is_admin = False
    g.debug = bool(app.debug)

    if g.user is not None:
        for t in g.user.teams:
            g.teams[t.team_id] = t.team.name
            g.teams_time_zones[t.team_id] = t.team.time_zone
            if t.is_founder():
                g.founder_teams.append(t.team_id)
                g.team_leader_teams.append(t.team_id)
            elif t.is_team_leader():
                g.team_leader_teams.append(t.team_id)

        g.is_admin = len(g.team_leader_teams) > 0


@app.route('/login/')
def login():
    return redirect(url_for('signin'))

@app.route('/signin/', defaults={'t':''}, methods=('GET', 'POST'))
@app.route('/signin/<t>/', methods=('GET', 'POST'))
@oid.loginhandler
def signin(t):
    if g.user is not None:
        return redirect(oid.get_next_url())
    if request.method == 'POST':
        if app.debug:
            openid = request.form.get('openid')
        else:
            openid = "http://steamcommunity.com/openid"
        if openid:
            return oid.try_login(openid, ask_for=['nickname','email'])

    n = request.url or oid.get_next_url()
    if n.endswith('signin') or n.endswith('signin/'):
        n = n.replace('signin', '')

    return rt('login.html', n=n, next=oid.get_next_url(), create=app.debug,
            error=oid.fetch_error())

@oid.after_login
def create_or_login(resp):
    session['openid'] = resp.identity_url
    session.permanent = True
    user = User.query.filter_by(openid=resp.identity_url).first()
    if user is not None:
        flash(u'You were successfully signed in.')
        g.user = user
        return redirect(oid.get_next_url())
    return redirect(url_for('create_profile', next=oid.get_next_url(),
                            name=resp.nickname, email=resp.email))

def require_login(url='signin', page=None):
    def decorator(target):
        def wrapper(*args, **kwargs):
            if g.user is None:
                flash(u'Please sign in to view this page.')
                return rt('login.html', next=oid.get_next_url(),
                        page=page, create=app.debug,
                        error=oid.fetch_error())
            return target(*args, **kwargs)
        wrapper.__name__ = target.__name__
        return wrapper
    return decorator

@app.route('/force_login/<username>')
def force_login(username):
    if app.debug:
        user = User.query.filter_by(name=username).first()
        if user is not None:
            flash(u'Logged in as %s' % username)
            session['force_login'] = username
            g.user = user
    return redirect(url_for('index'))

@app.route('/')
def index():
    if g.user:
        return my_matches()

    return rt('splash.html')

@app.route('/contact/', methods=('GET','POST'))
def contact():
    form = ContactForm()

    sent = False
    if form.validate_on_submit():
        body = form.comments.data
        msg = Message("[tardyrush] %s" % form.subject.data,
                      recipients=["phootsoldier@gmail.com"], #["contact@tardyrush.com"],
                      body=body,
                      sender=("tardyrush contact form",
                          "tardyrush@tardyrush.com"))

        mail.send(msg)
        
        flash(u"Your comments have been sent.  Thanks.")
        sent = True
        #return redirect(url_for("/'))

    return rt("contact.html", 
            page={'top':'contact', 'sub':''},
            form=form, sent=sent)

@app.route('/create_profile/', methods=('GET', 'POST'))
def create_profile():
    if g.user is not None or 'openid' not in session:
        return redirect(url_for('index'))

    names = set()
    emails = set()
    for u in User.query.all():
        if u.name is not None:
            names.add(u.name.lower())
        if u.email is not None:
            emails.add(u.email.lower())

    form = UserForm()
    form.name.validators[0].values = names
    form.email.validators[0].values = emails

    if form.validate_on_submit():
        user = User(name=form.name.data,
                    email=form.email.data,
                    openid=session['openid'])

        db.session.add(user)
        db.session.commit()
        flash(u'Profile successfully created')
        return redirect(oid.get_next_url())

    if not len(form.errors):
        form.name.data = request.values.get('name')
        form.email.data = request.values.get('email')

    form.next.data = oid.get_next_url()

    return rt('create_profile.html', form=form)

@app.route('/settings/', methods=('GET','POST'))
@require_login()
def settings():
    emails = set()
    #steam_ids = set()
    for u in User.query.all():
        if u.email is not None:
            emails.add(u.email.lower())
        #if u.steam_id is not None:
        #    steam_ids.add(u.steam_id.lower())

    if g.user.email is not None:
        email_lower = g.user.email.lower()
        if email_lower in emails:
            emails.remove(email_lower)

    #if g.user.steam_id is not None:
    #    steam_id_lower = g.user.steam_id.lower() 
    #    if steam_id_lower in steam_ids:
    #        steam_ids.remove(steam_id_lower)

    form = UserSettingsForm(request.form, obj=g.user)
    form.email.validators[0].values = emails
    #form.steam_id.validators[0].values = steam_ids

    if form.validate_on_submit():
        form.populate_obj(g.user)
        db.session.commit()
        babel_refresh()
        flash(u'Settings successfully updated.')
        return redirect(url_for('settings'))

    return rt('create_profile.html', settings=True, form=form)

@app.route('/logout')
@app.route('/signout')
def signout():
    session.pop('openid', None)
    session.pop('force_login', None)
    flash(u'You were signed out.')
    return redirect('/')


###############
@app.route('/match/')
@app.route('/matches/')
@app.route('/match/upcoming/')
@app.route('/matches/upcoming/')
def my_matches():
    if not g.user:
        return redirect(url_for('matches'))

    cutoff = datetime.datetime.utcnow() - datetime.timedelta(hours=1)
    matches = Match.query.\
            filter(Match.team_id.in_(g.teams.keys())).\
            filter(Match.date > cutoff).\
            options(eagerload('competition'), \
                    eagerload('server')).\
            order_by(Match.date.asc()).\
            order_by(Match.id.asc()).\
            all()

    return rt('show_all.html',
        page={'top':'my_matches', 'sub':'upcoming'},
        aform = MatchPlayerStatusForm(),
        matches=matches)

@app.route('/match/previous/')
def my_previous_matches():
    if not g.user:
        return redirect(url_for('matches'))

    cutoff = datetime.datetime.utcnow()
    matches = Match.query.\
            filter(Match.team_id.in_(g.teams.keys())).\
            filter(Match.date <= cutoff).\
            options(eagerload('competition'), \
                    eagerload('server')).\
            order_by(Match.date.asc()).\
            order_by(Match.id.asc()).\
            all()

    return rt('matches_public.html',
        page={'top':'my_matches', 'sub':'previous'},
        previous_only=True,
        previous=matches)

@app.route('/match/all/')
@app.route('/matches/all/')
def matches(team_id=0): # show all matches
    team = None
    if team_id: 
        if team_id not in g.teams:
            team = Team.query.filter_by(id=team_id).first()

            if not team:
                return redirect(url_for('matches'))

            page = {'top':'team', 'sub':'matches'}
        else:
            team = {'id' : team_id, 'name' : g.teams[team_id]}
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

    return rt('matches_public.html',
        page=page, team=team,
        upcoming=upcoming, previous=previous)

@app.route('/team/<int:team_id>/matches/')
@app.route('/teams/<int:team_id>/matches/')
def team_matches(team_id=0):
    return matches(team_id)

@app.route('/team/<int:team_id>/stats/')
@app.route('/teams/<int:team_id>/stats/')
def team_player_stats(team_id=0):
    team = Team.query.filter_by(id=team_id).first()

    if not team:
        return redirect(url_for('teams'))

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

    return rt('team_player_stats.html', 
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


# /team -> show all
# /team/add
# /team/1 -> show team
# /team/1/edit
# /team/1/delete

@app.route('/team/all/')
@app.route('/teams/all/')
def teams():
    return rt('teams.html',
            page={'top':'teams', 'sub':'all_teams'},
            all_teams=True,
            teams=Team.query.order_by(Team.name.asc()).all())


# show teams the current user is on
@app.route('/team/')
@app.route('/my_teams/')
@app.route('/teams/')
def my_teams():
    if len(g.teams):
        return show_team()

    return redirect(url_for('teams'))

    #teams = Team.query.\
    #        filter(Team.id.in_(g.teams.keys())).\
    #        order_by(Team.name.asc()).all()

    #if not len(teams):
    #    flash(u"""You are not on a team. 
    #              Join a team by clicking Join next to the team's name.
    #              Or create a team if you're a team leader.
    #              """)
    #    return redirect(url_for('teams'))

    #return rt('teams.html',
    #        page={'top': 'teams', 'sub': 'my_teams'},
    #        teams=teams)

@app.route('/team/<action>/', defaults={'team_id':-1}, methods=('GET','POST'))
@app.route('/team/<int:team_id>/', defaults={'action':''})
@app.route('/team/<int:team_id>/<action>/', methods=('GET','POST'))
def show_team(team_id=-1, action=''):
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
                return rt('teams.html', 
                        page={'top':'my_teams', 'sub':'all_my'},
                        teams=teams)
            return redirect(url_for('team'))

        if team_id > 0:
            team = Team.query.filter_by(id=team_id).first()
        else:
            team = None
 
        if not team:
            flash(u'Team not found')
            return redirect(url_for('team'))

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

                return redirect(url_for('show_team', team_id=team.id))

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
                        return redirect(url_for('show_team',team_id=team.id))

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
                    return redirect(url_for('show_team', 
                        team_id=team.id, action='edit'))

                return rt('create_team.html', team_id=team.id,
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
                        return redirect(url_for('show_team', 
                            team_id=team.id, action='edit'))

                return rt('create_team.html',
                        page={'top':'my_teams', 'sub':'edit'},
                        team_id=team.id, team=team,
                        players=players, form=form, players_form=players_form)

            elif action == 'delete':
                if request.method == 'POST':
                    db.session.delete(team)
                    db.session.commit()
                    flash(u'Team was successfuly deleted')
                    return redirect(url_for('teams'))

                flash(u'Team not found')
                return redirect(url_for('show_team', team_id=team.id))

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

        return rt('team.html', 
                page=page,
                wins=wins, losses=losses, draws=draws,
                team=team,
                players=players,
                leave_form=leave_form,
                join_form=join_form)

    return redirect(url_for('team'))

@app.route('/team/add', methods=('GET','POST'))
@require_login(page={'top':'teams','sub':'add_team'})
def add_team():
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
        return redirect(url_for('my_matches'))

    return rt('create_team.html', 
            page={'top': 'teams', 'sub': 'add_team'},
            adding=True,
            form=form)


# /match -> show all
# /match/new -> show form
# /match/1 -> show match 1
# /match/1/edit -> edit match 1
# /match/1/delete -> delete match 1
@app.route('/match/add/', methods=('GET','POST'))
@require_login(page={'top':'my_matches','sub':'add_match'})
def add_match():
    if not is_team_leader():
        flash(u'You must be a team leader to add a match.')
        return redirect(url_for('my_matches'))

    opponents = Opponent.query.\
            filter(Opponent.team_id.in_(g.team_leader_teams)).\
            order_by(Opponent.name.asc()).all()

    servers = Server.query.\
            filter(Server.team_id.in_(g.team_leader_teams)).\
            order_by('server_name')
    competitions = Competition.query.order_by('competition_name')

    form = MatchForm()
    form.team_id.choices = [ (t, g.teams[t]) for t in g.team_leader_teams ]
    form.competition_id.choices = [(c.id, c.name) for c in competitions ]
    form.server_id.choices = [ (s.id, s.name) for s in servers ]
    form.opponent_id.choices = [ (o.id, o.name) for o in opponents ]

    if request.method == 'GET':
        if request.values.get('new_opponent_id'):
            form.opponent_id.data = int(request.values.get('new_opponent_id'))
        elif request.values.get('new_server_id'):
            form.server_id.data = int(request.values.get('new_server_id'))

        form.date.data = datetime.datetime.combine((\
                    to_user_timezone(datetime.datetime.utcnow()) \
                        + datetime.timedelta(days=1))\
                        .date(),\
                    datetime.time(21))

    if form.validate_on_submit():
        if not is_team_leader(form.team_id.data):
            flash(u'Invalid team')
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
                    g.teams_time_zones[form.team_id.data])
           
            date_short = matches_datetime_format(date)
            team_date_short = matches_datetime_format_for_team(date, \
                    g.teams_time_zones[form.team_id.data])

            email_vars = { 'date' : matches_datetime_format_full(date),
                           'team_date' : team_date,
                           'date_short' : date_short,
                           'team_date_short' : team_date_short,
                           'team' : g.teams[form.team_id.data],
                           'opponent' : match.opponent.name,
                           'opponent_tag' : match.opponent.tag,
                           'competition' : match.competition.name,
                           'server' : match.server.name,
                           'address' : match.server.address,
                           'password' : match.password,
                           'comments' : match.comments,
                           'match_url' : abs_url_for('show_match',
                               match_id=match.id),
                           'settings_url' : abs_url_for('settings') }

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

            try:
                with mail.connect() as conn:
                    for p in players:
                        msg = Message(recipients=[p.email],
                                      body=message,
                                      subject=subject,
                                      sender=Sender)
                        conn.send(msg)
            except Exception, e:
                pass

            # now notify players of new match via forum post
            forum_post = ForumBotQueuedPost(team_id=match.team_id,
                                            game_id=match.competition.game_id,
                                            match_id=match.id,
                                            subject=team_subject,
                                            message=team_message)
            db.session.add(forum_post)
            db.session.commit()

            flash(u'The match was successfully added.')
            return redirect(url_for('my_matches'))

    oform = OpponentForm()
    sform = ServerForm()

    return rt('new.html', 
            page={'top':'my_matches', 'sub':'add_match'},
            adding=True,
            team_id=g.team_leader_teams[0],
            oform=oform,
            sform=sform,
            form=form)

@app.route('/match/<int:match_id>/', defaults={'action':''})
@app.route('/match/<int:match_id>/<action>/', methods=('GET','POST'))
@require_login()
def show_match(match_id, action):
    match = Match.query.filter_by(id=match_id).first()
    if not match:
        flash(u'Match not found')
        return redirect(url_for('my_matches'))

    if match.team_id not in g.teams:
        flash(u'You must be on this team to view this match.')
        return redirect(url_for('my_matches'))

    if match.date < datetime.datetime.utcnow():
        up_prev = 'previous'
    else:
        up_prev = 'upcoming'
 
    if action == 'edit':
        if not is_team_leader(match.team_id):
            flash(u'You must be a team leader to edit this match.')
            return redirect(url_for('my_matches'))

        servers = Server.query.\
                filter_by(team_id=match.team_id).\
                order_by('server_name')

        form = MatchForm(request.form, obj=match)
        form.competition_id.choices = [(c.id, c.name) for c in
                Competition.query.order_by('competition_name')]
        form.server_id.choices = [ (s.id, s.name) for s in servers ]
        form.team_id.choices = [ (t, g.teams[t]) for t in g.team_leader_teams ]
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
        elif request.method == 'POST':
            form.date.data = to_utc(form.date.data)

        if form.validate_on_submit():
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
            flash(u'Match was successfully updated')

            if request.values.get('from') == 'single':
                return redirect(url_for('show_match', match_id=match_id))

            return redirect(url_for('my_matches'))

        oform = OpponentForm()
        sform = ServerForm()

        return rt('new.html', form=form, players=players, 
                page={'top':'my_matches', 'sub':up_prev},
                when=up_prev,
                adding=False,
                oform=oform,
                sform=sform,
                team_id=g.team_leader_teams[0],
                match_id=match.id)
    elif action == 'delete':
        if not is_team_leader(match.team_id):
            flash(u'You must be a team leader to edit this match.')
            return redirect(url_for('my_matches'))

        if request.method == 'POST':
            db.session.delete(match)
            db.session.commit()
            flash(u'Match was successfully deleted')

        return redirect(url_for('my_matches'))
    elif action == 'status':
        if not is_on_current_team(match.team_id):
            flash(u'You must be on this team to change your status.')
            return redirect(url_for('my_matches'))

        if up_prev == 'previous':
            flash(u'You cannot change your status on a past match.')
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
                flash(u'Invalid status!')
            else:
                try:
                    mu = MatchPlayer.query.filter_by(match_id=match.id,
                                                     user_id=g.user.id).one()
                    mu.status = player_status
                except NoResultFound:
                    mu = MatchPlayer(match_id=match.id, user_id=g.user.id,
                                     status=player_status)
                except:
                    flash(u'Oops! There was an error!')
                    return redirect(url_for('my_matches'))

                mu.date_updated = datetime.datetime.utcnow()
                db.session.add(mu)
                db.session.commit()

                if request.values.get('api') == '1':
                    psp = pretty_match_player_status(player_status)
                    return jsonify(success=True,
                            csrf=form.csrf.data,
                            match_id=match.id,
                            user_id=g.user.id,
                            user_name=g.user.name,
                            player_status=player_status,
                            player_status_pretty=psp)

                if request.values.get('from') == 'single':
                    return redirect(url_for('show_match', match_id=match_id))
    else:
        return rt('match.html', 
                page={'top':'my_matches','sub':up_prev},
                when=up_prev,
                aform = MatchPlayerStatusForm(),
                match=match)

    return redirect(url_for('my_matches'))


@app.route('/team/<int:team_id>/server/add/', methods=('GET','POST'))
@require_login()
def add_server(team_id=0):
    if not is_team_leader(team_id):
        flash(u'You must be a team leader to add a server.')
        return redirect(url_for('my_teams'))

    servers = Server.query.\
            filter_by(team_id=team_id).\
            order_by(Server.name.asc()).\
            all()

    api = request.values.get('api') == '1'

    form = ServerForm()
    form.name.validators[0].values = [ s.name for s in servers ]
    if form.validate_on_submit():
        server = Server(team_id=team_id,
                        name=form.name.data,
                        address=form.address.data)
        db.session.add(server)
        db.session.commit()
        flash(u'The server was successfully added.')

        if api:
            return jsonify(success=True, server_id=server.id,
                    csrf=form.csrf.data,
                    server_name=server.name)

        if form.f.data == 'add_match':
            return redirect(url_for('add_match', new_server_id=server.id))
        elif form.f.data:
            return redirect(url_for('show_match', action='edit',
                match_id=int(form.f.data), new_server_id=server.id))

        return redirect(url_for('admin',team_id=team_id))

    form.f.data = request.values.get('f') or ''

    return rt('server_form.html',
            page={'top':'my_teams', 'sub':'admin'},
            team={'id':team_id,'name':g.teams[team_id]},
            adding=True, form=form)

@app.route('/team/<int:team_id>/server/<int:server_id>/<action>/', methods=('GET','POST'))
@require_login()
def server(team_id, server_id, action):
    if not is_team_leader(team_id):
        flash(u'You must be a team leader to add a server.')
        return redirect(url_for('my_teams'))

    server = Server.query.filter_by(id=server_id).first()

    if not server or not is_team_leader(server.team_id):
        flash(u'Server not found.')
        return redirect(url_for('my_teams'))

    if action == 'edit':
        servers = Server.query.\
                filter_by(team_id=team_id).\
                order_by(Server.name.asc()).\
                all()

        form = ServerForm(request.form, obj=server)
        form.name.validators[0].values = [ s.name for s in servers if s.id != \
                server_id ]

        if form.validate_on_submit():
            form.populate_obj(server)
            db.session.commit()
            flash(u'The server was successfully updated.')
        else:
            return rt('server_form.html',
                    team={'id':team_id, 'name':g.teams[team_id]},
                    page={'top':'my_teams', 'sub':'admin'},
                    server_id=server_id,
                    adding=False, form=form)
    elif action == 'delete':
        if request.method == 'POST':
            db.session.delete(server)
            db.session.commit()
            flash(u'The server was successfully deleted.')

    return redirect(url_for('admin',team_id=team_id))







@app.route('/team/<int:team_id>/opponent/add/', methods=('GET','POST'))
@require_login()
def add_opponent(team_id=0):
    if not is_team_leader(team_id):
        flash(u'You must be a team leader to add an opponent.')
        return redirect(url_for('my_teams'))

    opponents = Opponent.query.\
            filter_by(team_id=team_id).\
            order_by(Opponent.name.asc()).\
            all()

    api = request.values.get('api') == '1'

    form = OpponentForm()
    form.name.validators[0].values = [ o.name for o in opponents ]
    if form.validate_on_submit():
        opponent = Opponent(team_id=team_id,
                            name=form.name.data,
                            tag=form.tag.data)
        db.session.add(opponent)
        db.session.commit()
        flash(u'The opponent was successfully added.')

        if api:
            return jsonify(success=True, opponent_id=opponent.id,
                    csrf=form.csrf.data,
                    opponent_name=opponent.name)

        if form.f.data == 'add_match':
            return redirect(url_for('add_match', new_opponent_id=opponent.id))
        elif form.f.data:
            return redirect(url_for('show_match', action='edit',
                match_id=int(form.f.data), new_opponent_id=opponent.id))

        return redirect(url_for('admin',team_id=team_id))

    form.f.data = request.values.get('f') or ''

    return rt('opponent_form.html',
            team={'id' : team_id, 'name':g.teams[team_id]},
            page={'top':'my_teams', 'sub':'admin'},
            adding=True, form=form)


@app.route('/team/<int:team_id>/opponent/<int:opponent_id>/<action>/',\
        methods=('GET','POST'))
@require_login()
def opponent(team_id, opponent_id, action):
    if not is_team_leader(team_id):
        flash(u'You must be a team leader to add an opponent.')
        return redirect(url_for('my_teams'))

    opponent = Opponent.query.filter_by(id=opponent_id).first()

    if not opponent or not is_team_leader(opponent.team_id) or team_id !=\
            opponent.team_id:
        flash(u'Opponent not found.')
        return redirect(url_for('my_teams'))

    if action == 'edit':
        opponents = Opponent.query.\
                filter_by(team_id=team_id).\
                order_by(Opponent.name.asc()).\
                all()

        form = OpponentForm(request.form, obj=opponent)
        form.name.validators[0].values = [ o.name for o in opponents if o.id\
                != opponent_id ]
        if form.validate_on_submit():
            form.populate_obj(opponent)
            db.session.commit()
            flash(u'The opponent was successfully updated.')
        else:
            return rt('opponent_form.html',
                    page={'top':'my_teams', 'sub':'admin'},
                    team={'id' : team_id, 'name':g.teams[team_id]},
                    opponent_id=opponent_id,
                    adding=False, form=form)
    elif action == 'delete':
        if request.method == 'POST':
            db.session.delete(opponent)
            db.session.commit()
            flash(u'The opponent was successfully deleted.')

    return redirect(url_for('admin',team_id=team_id))


@app.route('/team/<int:team_id>/admin/')
@app.route('/teams/<int:team_id>/admin/')
def admin(team_id=0):
    if not team_id or not is_team_leader(team_id):
        flash(u'You must be a team leader to administrate the team.')
        return redirect(url_for('my_teams'))
    
    opponents = Opponent.query.\
            filter_by(team_id=team_id).\
            order_by(Opponent.name.asc()).\
            all()

    servers = Server.query.\
            filter_by(team_id=team_id).\
            order_by(Server.name.asc()).\
            all()

    forum_bots = ForumBot.query.\
            filter_by(team_id=team_id).\
            order_by(ForumBot.id.desc()).\
            all()

    return rt('team_admin.html',
            page={'top':'my_teams','sub':'admin'},
            team={'id' : team_id, 'name':g.teams[team_id]},
            opponents=opponents,
            servers=servers,
            forum_bots=forum_bots)
    
@app.route('/team/<int:team_id>/forum_bots/add/', methods=('GET','POST'))
@require_login()
def add_forum_bot(team_id=0):
    if not team_id or not is_team_leader(team_id):
        flash(u'You must be a team leader to add a forum helper.')
        return redirect(url_for('my_teams'))

    form = ForumBotForm()
    form.game_id.choices = [ (-1, "Any match is added") ]
    form.game_id.choices += [ (game.id, "A %s match is added" % game.name) for \
            game in Game.query.all() ]
    if form.validate_on_submit():
        if form.game_id.data <= 0:
            game_id = None
        else:
            game_id = form.game_id.data

        forum_bot = ForumBot(team_id=team_id,
                             game_id=game_id,
                             type=form.type.data,
                             url=form.url.data,
                             forum_id=form.forum_id.data,
                             user_name=form.user_name.data,
                             password=form.password.data)
        db.session.add(forum_bot)
        db.session.commit()
        flash(u'The forum helper was successfully added.')
        return redirect(url_for('admin',team_id=team_id))

    return rt('forum_bot_form.html',
            team={'id' : team_id, 'name':g.teams[team_id]},
            page={'top':'my_teams', 'sub':'admin'},
            adding=True, form=form)





@app.route('/team/<int:team_id>/forum_helper/<int:forum_bot_id>/<action>/', methods=('GET','POST'))
@require_login()
def forum_bot(team_id,forum_bot_id, action):
    if not is_team_leader(team_id):
        flash(u'You must be a team leader to add a forum helper.')
        return redirect(url_for('my_teams'))

    forum_bot = ForumBot.query.filter_by(id=forum_bot_id).first()

    if not forum_bot or team_id != forum_bot.team_id:
        flash(u'Forum helper not found.')
        return redirect(url_for('my_teams'))

    if action == 'edit':
        form = ForumBotForm(request.form, obj=forum_bot)
        # can't change the team to which the forum_bot belongs when editing
        form.game_id.choices = [ (-1, "Any match is added") ]
        form.game_id.choices += [ (game.id, "A %s match is added" % game.name) for \
                game in Game.query.all() ]
        if form.validate_on_submit():
            if form.game_id.data <= 0:
                form.game_id.data = None
            else:
                form.game_id.data = form.game_id.data
            form.populate_obj(forum_bot)
            db.session.commit()
            flash(u'The forum helper was successfully updated.')
        else:
            return rt('forum_bot_form.html',
                    page={'top':'my_teams', 'sub':'admin'},
                    team={'id' : team_id, 'name':g.teams[team_id]},
                    forum_bot_id=forum_bot_id,
                    adding=False, form=form)
    elif action == 'delete':
        if request.method == 'POST':
            db.session.delete(forum_bot)
            db.session.commit()
            flash(u'The forum helper was successfully deleted.')

    return redirect(url_for('admin', team_id=team_id))



@app.route('/results/add/', defaults={'cmatch_id':0,'action':''}, \
                            methods=('GET','POST'))
@app.route('/results/<int:cmatch_id>/<action>/', methods=('GET','POST'))
@require_login(page={'top':'my_matches','sub':'previous'})
def add_results(cmatch_id, action):
    if not is_team_leader():
        flash(u'You must be a team leader to add results.')
        return redirect(url_for('my_matches'))

    if cmatch_id > 0:
        corr_match_id = cmatch_id
        adding = False

        corr_match = CompletedMatch.query.filter_by(id=cmatch_id).first()
        if not corr_match:
            flash(u'Results not found.')
            return redirect(url_for('my_matches'))
    else:
        cmatch_id = 0
        adding = True
        corr_match_id = request.values.get('match_id')
        corr_match = Match.query.filter_by(id=corr_match_id).\
                filter(Match.team_id.in_(g.team_leader_teams)).first()

        if not corr_match:
            flash(u'Corresponding availability match not found.')
            return redirect(url_for('my_matches'))

        if corr_match.date > datetime.datetime.utcnow():
            flash(u'Cannot add results to match in the future.')
            return redirect(url_for('my_matches'))

        if len(corr_match.results):
            flash(u'Results have already been added.')
            return redirect(url_for('add_results',
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
                return redirect(url_for('my_previous_matches'))

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
                return redirect(url_for('my_previous_matches'))

    return rt('completed_matches/new.html', 
            page={'top':'my_matches', 'sub':'previous'},
            adding=adding,
            player_choices=player_choices,
            map_choices=map_choices,
            side_choices=side_choices,
            gametype_choices=gametype_choices,
            form=form)

@app.route('/results/<int:cmatch_id>/')
def show_completed_match(cmatch_id):
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


