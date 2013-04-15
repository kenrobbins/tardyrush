from flask import Module, g, request, flash, url_for
from tardyrush import db
from tardyrush.views import require_login
from tardyrush.helpers import rt, jsonify, abs_url_for, redirect
from tardyrush.helpers.filters import *
from tardyrush.helpers.teams import *
from tardyrush.models import \
        Opponent, OpponentForm, ServerForm, Server, Game, \
        ForumBotQueuedPost, ForumBot, ForumBotForm

team_admin = Module(__name__)

@team_admin.route('/team/<int:team_id>/server/add/', methods=('GET','POST'))
@require_login()
def add_server(team_id=0):
    if not g.user.is_team_leader(team_id):
        flash(u'You must be a team leader to add a server.', 'error')
        return redirect(url_for('teams.my_teams'))

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
        flash(u'The server was successfully added.', 'success')

        if api:
            return jsonify(success=True, server_id=server.id,
                    csrf=form.csrf_token.data,
                    server_name=server.name)

        if form.f.data == 'add_match':
            return redirect(url_for('matches.add', new_server_id=server.id))
        elif form.f.data:
            return redirect(url_for('matches.show', action='edit',
                match_id=int(form.f.data), new_server_id=server.id))

        return redirect(url_for('index',team_id=team_id))

    form.f.data = request.values.get('f') or ''

    return rt('team_admin/server_form.html',
            page={'top':'my_teams', 'sub':'admin'},
            team={'id':team_id,'name':g.user.teams[team_id].name},
            adding=True, form=form)

@team_admin.route('/team/<int:team_id>/server/<int:server_id>/<action>/', methods=('GET','POST'))
@require_login()
def server(team_id, server_id, action):
    if not g.user.is_team_leader(team_id):
        flash(u'You must be a team leader to add a server.', 'error')
        return redirect(url_for('teams.my_teams'))

    server = Server.query.filter_by(id=server_id).first()

    if not server or not g.user.is_team_leader(server.team_id):
        flash(u'Server not found.', 'error')
        return redirect(url_for('teams.my_teams'))

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
            flash(u'The server was successfully updated.', 'success')
        else:
            return rt('team_admin/server_form.html',
                    team={'id':team_id, 'name':g.user.teams[team_id].name},
                    page={'top':'my_teams', 'sub':'admin'},
                    server_id=server_id,
                    adding=False, form=form)
    elif action == 'delete':
        if request.method == 'POST':
            db.session.delete(server)
            db.session.commit()
            flash(u'The server was successfully deleted.', 'success')

    return redirect(url_for('index',team_id=team_id))


@team_admin.route('/team/<int:team_id>/opponent/add/', methods=('GET','POST'))
@require_login()
def add_opponent(team_id=0):
    if not g.user.is_team_leader(team_id):
        flash(u'You must be a team leader to add an opponent.', 'error')
        return redirect(url_for('teams.my_teams'))

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
        flash(u'The opponent was successfully added.', 'success')

        if api:
            return jsonify(success=True, opponent_id=opponent.id,
                    csrf=form.csrf_token.data,
                    opponent_name=opponent.name)

        if form.f.data == 'add_match':
            return redirect(url_for('matches.add', new_opponent_id=opponent.id))
        elif form.f.data:
            return redirect(url_for('matches.show', action='edit',
                match_id=int(form.f.data), new_opponent_id=opponent.id))

        return redirect(url_for('index',team_id=team_id))

    form.f.data = request.values.get('f') or ''

    return rt('team_admin/opponent_form.html',
            team={'id' : team_id, 'name':g.user.teams[team_id].name},
            page={'top':'my_teams', 'sub':'admin'},
            adding=True, form=form)


@team_admin.route('/team/<int:team_id>/opponent/<int:opponent_id>/<action>/',\
        methods=('GET','POST'))
@require_login()
def opponent(team_id, opponent_id, action):
    if not g.user.is_team_leader(team_id):
        flash(u'You must be a team leader to add an opponent.', 'error')
        return redirect(url_for('teams.my_teams'))

    opponent = Opponent.query.filter_by(id=opponent_id).first()

    if not opponent or not g.user.is_team_leader(opponent.team_id) \
            or team_id != opponent.team_id:
        flash(u'Opponent not found.', 'error')
        return redirect(url_for('teams.my_teams'))

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
            flash(u'The opponent was successfully updated.', 'success')
        else:
            return rt('team_admin/opponent_form.html',
                    page={'top':'my_teams', 'sub':'admin'},
                    team={'id' : team_id, 'name':g.user.teams[team_id].name},
                    opponent_id=opponent_id,
                    adding=False, form=form)
    elif action == 'delete':
        if request.method == 'POST':
            db.session.delete(opponent)
            db.session.commit()
            flash(u'The opponent was successfully deleted.', 'success')

    return redirect(url_for('index',team_id=team_id))


@team_admin.route('/team/<int:team_id>/admin/')
def index(team_id=0):
    if not team_id or not g.user.is_team_leader(team_id):
        flash(u'You must be a team leader to administrate the team.', 'error')
        return redirect(url_for('teams.my_teams'))

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

    return rt('team_admin/index.html',
            page={'top':'my_teams','sub':'admin'},
            team={'id' : team_id, 'name':g.user.teams[team_id].name},
            opponents=opponents,
            servers=servers,
            forum_bots=forum_bots)

@team_admin.route('/team/<int:team_id>/forum_bots/add/', methods=('GET','POST'))
@require_login()
def add_forum_bot(team_id=0):
    if not team_id or not g.user.is_team_leader(team_id):
        flash(u'You must be a team leader to add a forum helper.', 'error')
        return redirect(url_for('teams.my_teams'))

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
        flash(u'The forum helper was successfully added.', 'success')
        return redirect(url_for('index',team_id=team_id))

    return rt('team_admin/forum_bot_form.html',
            team={'id' : team_id, 'name':g.user.teams[team_id].name},
            page={'top':'my_teams', 'sub':'admin'},
            adding=True, form=form)


@team_admin.route('/team/<int:team_id>/forum_helper/<int:forum_bot_id>/<action>/', methods=('GET','POST'))
@require_login()
def forum_bot(team_id,forum_bot_id, action):
    if not g.user.is_team_leader(team_id):
        flash(u'You must be a team leader to add a forum helper.', 'error')
        return redirect(url_for('teams.my_teams'))

    forum_bot = ForumBot.query.filter_by(id=forum_bot_id).first()

    if not forum_bot or team_id != forum_bot.team_id:
        flash(u'Forum helper not found.', 'error')
        return redirect(url_for('teams.my_teams'))

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
            flash(u'The forum helper was successfully updated.', 'success')
        else:
            return rt('team_admin/forum_bot_form.html',
                    page={'top':'my_teams', 'sub':'admin'},
                    team={'id' : team_id, 'name':g.user.teams[team_id].name},
                    forum_bot_id=forum_bot_id,
                    adding=False, form=form)
    elif action == 'delete':
        if request.method == 'POST':
            db.session.delete(forum_bot)
            db.session.commit()
            flash(u'The forum helper was successfully deleted.', 'success')

    return redirect(url_for('index', team_id=team_id))

