from datetime import datetime
from flask import Module, g, session, flash, request, url_for
from flaskext.babel import (refresh as babel_refresh,
                            to_user_timezone,
                            format_datetime)
from tardyrush import oid, app, db
from tardyrush.views import require_login
from tardyrush.helpers import rt, jsonify, redirect
from tardyrush.models import User, UserForm, UserSettingsForm, UserTimeZoneForm


account = Module(__name__)


@oid.after_login
def create_or_login(resp):
    session['openid'] = resp.identity_url
    session.permanent = True

    user = User.query.filter_by(openid=resp.identity_url).first()
    if user is not None:
        flash(u'You were successfully signed in.', 'success')
        g.user = user
        return redirect(oid.get_next_url())

    return redirect(url_for('create_profile',
                            next=oid.get_next_url(),
                            name=resp.nickname,
                            email=resp.email))

@account.route('/signin/', defaults={'t':''}, methods=('GET', 'POST'))
@account.route('/signin/<t>/', methods=('GET', 'POST'))
@oid.loginhandler
def signin(t):
    if not g.user.is_guest:
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
            flash(u'Logged in as %s' % username, 'success')
            session['force_login'] = username
            g.user = user
        return redirect(url_for('create_profile'))
    return redirect(url_for('.index'))

@account.route('/create_profile/', methods=('GET', 'POST'))
def create_profile():
    if app.debug and 'openid' not in session:
        session['openid'] = 'test'

    if not g.user.is_guest or 'openid' not in session:
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
        flash(u'Profile successfully created', 'success')
        return redirect(oid.get_next_url())

    if not len(form.errors):
        form.name.data = request.values.get('name')
        form.email.data = request.values.get('email')

    form.next.data = oid.get_next_url()

    return rt('account/create.html', form=form)

@account.route('/settings/update_time_zone/', methods=('POST',))
@require_login()
def update_time_zone():
    form = UserTimeZoneForm(request.form, obj=g.user)

    if form.validate_on_submit():
        form.populate_obj(g.user)
        db.session.commit()
        babel_refresh()
        flash(u'Your time zone was successfully updated.', 'success')

        now = to_user_timezone(datetime.utcnow())
        user_tz_names = (format_datetime(now, 'zzzz'), format_datetime(now, 'zzz'))

        return jsonify(success=True, time_zone=form.time_zone.data,
                csrf=form.csrf_token.data, user_tz_names=user_tz_names)

    flash(u'There was an error updating your time zone.', 'error')
    return jsonify(success=False)

@account.route('/settings/', methods=('GET','POST'))
@require_login()
def settings():
    emails = set()
    for u in User.query.all():
        if u.email is not None:
            emails.add(u.email.lower())

    if g.user.email is not None:
        email_lower = g.user.email.lower()
        if email_lower in emails:
            emails.remove(email_lower)

    form = UserSettingsForm(request.form, obj=g.user)
    form.email.validators[0].values = emails

    if form.validate_on_submit():
        form.populate_obj(g.user)
        db.session.commit()
        babel_refresh()
        flash(u'Settings successfully updated.', 'success')
        return redirect(url_for('settings'))

    return rt('account/create.html', settings=True, form=form)

@account.route('/signout')
def signout():
    session.pop('openid', None)
    session.pop('force_login', None)
    session.clear()
    flash(u'You were signed out.', 'info')
    return redirect('/')
