from flask import Module, g, session, flash, request, url_for
from flaskext.babel import refresh as babel_refresh
from tardyrush import oid, app, db
from tardyrush.views import require_login
from tardyrush.helpers import rt, jsonify, abs_url_for, redirect
from tardyrush.helpers.filters import *
from tardyrush.helpers.teams import *
from tardyrush.models import User, UserForm, UserSettingsForm

account = Module(__name__)

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

@account.route('/login/')
def login():
    return redirect(url_for('signin'))

@account.route('/signin/', defaults={'t':''}, methods=('GET', 'POST'))
@account.route('/signin/<t>/', methods=('GET', 'POST'))
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

    return rt('account/login.html', n=n, next=oid.get_next_url(), create=app.debug,
            error=oid.fetch_error())

@account.route('/force_login/<username>')
def force_login(username):
    if app.debug:
        user = User.query.filter_by(name=username).first()
        if user is not None:
            flash(u'Logged in as %s' % username)
            session['force_login'] = username
            g.user = user
    return redirect(url_for('.index'))

@account.route('/create_profile/', methods=('GET', 'POST'))
def create_profile():
    if g.user is not None or 'openid' not in session:
        return redirect(url_for('.index'))

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

    return rt('account/create.html', form=form)

@account.route('/settings/', methods=('GET','POST'))
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

    return rt('account/create.html', settings=True, form=form)

@account.route('/logout')
@account.route('/signout')
def signout():
    session.pop('openid', None)
    session.pop('force_login', None)
    flash(u'You were signed out.')
    return redirect('/')

