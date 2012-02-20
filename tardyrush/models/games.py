from tardyrush import db

from flaskext.wtf import Form, TextField, IntegerField, DateTimeField, \
        TextAreaField, HiddenField, SelectField, FormField, FieldList, \
        BooleanField, Length, NumberRange, Optional, Required, widgets, \
        ValidationError

from helpers import *
from inputs import *
from fields import *

class Competition(db.Model):
    __tablename__ = 'competitions'

    id = create_id_column('competition')
    name = create_name_column('competition')
    abbr = db.Column('abbreviation', db.String(255), nullable=False)
    url = db.Column('url', db.String(255), nullable=False)
    game_id = db.Column('game_id', id_type, db.ForeignKey('games.game_id'), \
            nullable=False)
    game = db.relation("Game")

class Game(db.Model):
    __tablename__ = 'games'
    id = create_id_column('game')
    name = create_name_column('game')
    abbr = db.Column('abbreviation', db.String(255), nullable=False, 
                     unique=True)
    thumbnail_url = db.Column('thumbnail_column', db.String(255),
                              nullable=True)
    server_copy_format = db.Column('server_copy_format', db.String(255),
                                   nullable=True)
    stats_columns = db.Column('stats_columns', db.String(255), nullable=True)

    def uses_stats_column(self, column):
        cols = self.stats_columns.split(',')
        return column in cols

class GameType(db.Model):
    __tablename__ = 'gametypes'
    id = create_id_column('gametype')
    game_id = db.Column('game_id', id_type, db.ForeignKey('games.game_id'), \
            nullable=False)
    name = create_name_column('gametype')

class Map(db.Model):
    __tablename__ = 'maps'
    id = create_id_column('map')
    game_id = db.Column('game_id', id_type, db.ForeignKey('games.game_id'), \
            nullable=False)
    name = create_name_column('map')

class Side(db.Model):
    __tablename__ = 'sides'
    id = create_id_column('side')
    game_id = db.Column('game_id', id_type, db.ForeignKey('games.game_id'), \
            nullable=False)
    name = create_name_column('side')



