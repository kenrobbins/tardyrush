import logging

from logging import Formatter

from flask import Flask
from flaskext.babel import Babel
from flask.ext.sqlalchemy import SQLAlchemy
from flask_mail import Mail
from flask_openid import OpenID

from tardyrush.helpers.consts import *

app = Flask(__name__)
app.config.from_pyfile('tardyrush.cfg')

db = SQLAlchemy(app)
oid = OpenID(app)
babel = Babel(app)
mail = Mail(app)

# modules

from tardyrush.views.teams import teams
from tardyrush.views.matches import matches
from tardyrush.views.team_admin import team_admin
from tardyrush.views.account import account
from tardyrush.views.results import results

app.register_module(teams)
app.register_module(matches)
app.register_module(team_admin)
app.register_module(account)
app.register_module(results)

# db helpers

def init_db():
    db.create_all()

def destroy_db():
    db.drop_all()


ADMINS = ContactRecipients
if not app.debug:
    from logging.handlers import SMTPHandler
    mail_handler = SMTPHandler('127.0.0.1',
                               'tardyrush@tardyrush.com',
                               ADMINS, 'tardyrush exception')
    mail_handler.setLevel(logging.ERROR)
    app.logger.addHandler(mail_handler)

    mail_handler.setFormatter(Formatter('''
Message type:       %(levelname)s
Location:           %(pathname)s:%(lineno)d
Module:             %(module)s
Function:           %(funcName)s
Time:               %(asctime)s

Message:

%(message)s
'''))

from logging.handlers import RotatingFileHandler
file_handler = RotatingFileHandler('/tmp/tardyrush.app.log')
file_handler.setLevel(logging.INFO)
app.logger.addHandler(file_handler)

file_handler.setFormatter(Formatter(
    '%(asctime)s %(levelname)s: %(message)s '
    '[in %(pathname)s:%(lineno)d]'
))

