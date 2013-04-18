import pytz

from flask import g, session, url_for, flash
from flask_mail import Message

from tardyrush import app, babel, oid, mail
from tardyrush.helpers import rt, redirect
from tardyrush.helpers import consts
from tardyrush.models import User, ContactForm

@babel.timezoneselector
def get_timezone():
    if g.user and g.user.time_zone in pytz.common_timezones:
        return g.user.time_zone
    return consts.DefaultTimeZone

@app.before_request
def lookup_current_user():
    if app.debug and 'force_login' in session:
        g.user = User.query.filter_by(name=session['force_login']).first()
    elif 'openid' in session:
        g.user = User.query.filter_by(openid=session['openid']).first()
    else:
        g.user = User.create_guest_user()


def require_login(url='signin', page=None):
    def decorator(target):
        def wrapper(*args, **kwargs):
            if g.user.is_guest:
                flash(u'Please sign in to view this page.', 'info')
                return rt('account/login.html', next=oid.get_next_url(),
                        page=page, create=app.debug,
                        error=oid.fetch_error())
            return target(*args, **kwargs)
        wrapper.__name__ = target.__name__
        return wrapper
    return decorator


@app.route('/')
def index():
    if not g.user.is_guest:
        return redirect(url_for('matches.my_matches'))

    return rt('splash.html')

@app.route('/contact/', methods=('GET','POST'))
def contact():
    form = ContactForm()

    sent = False
    if form.validate_on_submit():
        body = "Subject: %s\n\nBody:\n%s" % (form.email.data, form.comments.data)
        msg = Message("[tardyrush] %s" % form.subject.data,
                      recipients=consts.ContactRecipients,
                      body=body,
                      sender=("tardyrush contact form",
                          "tardyrush@tardyrush.com"))

        mail.send(msg)

        flash(u"Your comments have been sent. Thanks.", "success")
        sent = True

    return rt("contact.html",
            page={'top':'contact', 'sub':''},
            form=form, sent=sent)

@app.route('/about/')
def about():
    return rt("about.html", page={'top':'about', 'sub':''})
