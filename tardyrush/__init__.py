from flask import Flask
from flaskext.sqlalchemy import SQLAlchemy
from flaskext.openid import OpenID
from flaskext.mail import Mail
from flaskext.babel import Babel

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

