from flask import Flask
from flaskext.sqlalchemy import SQLAlchemy

app = Flask(__name__)
app.config.from_pyfile('tardyrush.cfg')

db = SQLAlchemy(app)

def init_db():
    db.create_all()

def destroy_db():
    db.drop_all()

import tardyrush.models
import tardyrush.views
