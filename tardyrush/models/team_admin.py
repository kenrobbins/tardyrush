from tardyrush import db

from flask.ext.wtf import Form, TextField, IntegerField, DateTimeField, \
        TextAreaField, HiddenField, SelectField, FormField, FieldList, \
        BooleanField, Length, NumberRange, Optional, Required

from helpers import *
from inputs import *
from fields import *
from validators import Unique

from matches import Match
from teams import Team

class Server(db.Model):
    __tablename__ = 'servers'

    id = create_id_column('server')
    name = create_name_column('server', unique=False)
    address = db.Column('address', db.String(255), nullable=False)
    team_id = db.Column('team_id', db.Integer(unsigned=True),
            db.ForeignKey('teams.team_id'), index=True, nullable=False)

    matches = db.relation(Match, primaryjoin=Match.server_id == id,
            cascade="delete")
    team = db.relation("Team", primaryjoin="Team.id == Server.team_id")

    __table_args__  = ( db.UniqueConstraint("team_id", "server_name"), {} ) 

class ServerForm(Form):
    name = StrippedTextField(u'Server Name', \
            validators=[Unique(), Length(min=0,max=100), Required()])
    address = StrippedTextField(u'Address', \
            validators=[Length(min=0,max=100), Required()])
    f = HiddenField()

class Opponent(db.Model):
    __tablename__ = 'opponents'
    id = create_id_column('opponent')
    name = create_name_column('opponent',unique=False)
    tag = db.Column('tag', db.String(255), nullable=False)
    team_id = db.Column('team_id', db.Integer(unsigned=True),
            db.ForeignKey('teams.team_id'), index=True, nullable=False)

    matches = db.relation(Match,
            primaryjoin=Match.opponent_id == id, cascade="delete")
    team = db.relation("Team", primaryjoin="Team.id == Opponent.team_id")

    __table_args__  = ( db.UniqueConstraint("team_id", "opponent_name"), {} ) 

class OpponentForm(Form):
    name = StrippedTextField(u'Opponent Name', \
            validators=[Unique(), Length(min=0,max=100), Required()])
    tag = StrippedTextField(u'Tag', \
            validators=[Length(min=0,max=20), Required()])
    f = HiddenField()




class ForumBot(db.Model):
    __tablename__ = 'forum_bots'

    id = create_id_column('forum_bot')
    type = db.Column('type', db.Integer(unsigned=True), nullable=False)
    url = db.Column('url', db.String(255), nullable=False)
    forum_id = db.Column('forum_id', db.Integer(unsigned=True), nullable=True)
    user_name = db.Column('user_name', db.String(255), nullable=True)
    password = db.Column('password', db.String(255), nullable=True)

    team_id = db.Column('team_id', db.Integer(unsigned=True),
            db.ForeignKey('teams.team_id'), index=True, nullable=False)
    game_id = db.Column('game_id', id_type, db.ForeignKey('games.game_id'), \
            index=True, nullable=True)

    TypeVBulletin3_7 = 1

    TypePrettyNames = { TypeVBulletin3_7 : "vBulletin 3.7" }
    TypeChoices = [ (TypeVBulletin3_7, "vBulletin 3.7") ]

    team = db.relation("Team", primaryjoin="Team.id == ForumBot.team_id")
    game = db.relation("Game", primaryjoin="Game.id == ForumBot.game_id")

class ForumBotForm(Form):
    type = SelectField(u'Forum Type', coerce=int, choices=ForumBot.TypeChoices)
    url = StrippedTextField(u'Forums URL', \
            validators=[Length(min=0,max=255), Required()])
    forum_id = IntegerField(u'Forum ID', default=1,
            validators=[NumberRange(min=0), Required()])
    user_name = StrippedTextField(u'User Name', \
            validators=[Length(min=0,max=200), Required()])
    password = StrippedTextField(u'Password', \
            validators=[Length(min=0,max=200), Required()])

    game_id = SelectField(u'Post when...', coerce=int, validators=[Required()])

class ForumBotQueuedPost(db.Model):
    __tablename__ = 'forum_bot_queued_posts'

    id = create_id_column('forum_bot_queued_post')
    date_created = db.Column('date_created', db.DateTime, nullable=False,
            default=datetime.utcnow())
    team_id = db.Column('team_id', db.Integer(unsigned=True),
            db.ForeignKey('teams.team_id'), index=True, nullable=False)
    game_id = db.Column('game_id', db.Integer(unsigned=True),
            db.ForeignKey('games.game_id'),
            nullable=False)
    match_id = db.Column('match_id', id_type, \
            db.ForeignKey('matches.match_id'), nullable=False)
    subject = db.Column('subject', db.String(255), nullable=False)
    message = db.Column('message', db.Text, nullable=False)

    match = db.relation('Match',
            primaryjoin="Match.id == ForumBotQueuedPost.match_id")

    team = db.relation(Team,
            primaryjoin="Team.id == ForumBotQueuedPost.team_id")

