from flask import Flask
from flaskext.sqlalchemy import SQLAlchemy
from flaskext.openid import OpenID
from flaskext.mail import Mail
from flaskext.babel import Babel

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
    import logging
    from logging.handlers import SMTPHandler
    mail_handler = SMTPHandler('127.0.0.1',
                               'tardyrush@tardyrush.com',
                               ADMINS, 'tardyrush exception')
    mail_handler.setLevel(logging.ERROR)
    app.logger.addHandler(mail_handler)

    from logging import Formatter
    mail_handler.setFormatter(Formatter('''
Message type:       %(levelname)s
Location:           %(pathname)s:%(lineno)d
Module:             %(module)s
Function:           %(funcName)s
Time:               %(asctime)s

Message:

%(message)s
'''))

