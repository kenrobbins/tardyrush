from tardyrush import db

from flaskext.wtf import Form, TextField, IntegerField, DateTimeField, \
        TextAreaField, HiddenField, SelectField, FormField, FieldList, \
        BooleanField, Length, NumberRange, Optional, Required

from helpers import *
from inputs import *
from fields import *

class MatchPlayer(db.Model):
    __tablename__ = 'match_players'

    match_id = db.Column('match_id', db.Integer(unsigned=True), \
            db.ForeignKey('matches.match_id'), nullable=False, primary_key=True)
    user_id = db.Column('user_id', db.Integer(unsigned=True), \
            db.ForeignKey('users.user_id'), nullable=False, primary_key=True)
    status = db.Column('status', db.Integer(unsigned=True), nullable=False)
    date_updated = db.Column('date_updated', db.DateTime, nullable=False)
    #lineup_slot = db.Column('lineup_slot', db.Integer(unsigned=True),
    #        nullable=False, server_default='0')

    user = db.relation('User')

    StatusAvailable = 10
    StatusMaybe = 20
    StatusUnavailable = 30

    StatusPrettyNames = { StatusAvailable : "Available",
                          StatusMaybe : "Maybe",
                          StatusUnavailable : "Unavailable" }

    StatusChoices = [ (StatusAvailable, "Available"),
                      (StatusMaybe, "Maybe"),
                      (StatusUnavailable, "Unavailable") ]

    def __init__(self, match_id=0, user_id=0, status=StatusAvailable):
        self.match_id = match_id
        self.user_id = user_id
        self.status = status

class MatchPlayerForm(Form):
    user_id = HiddenIntegerField(u'User ID', validators=[NumberRange(min=1),
            Required()])
    status = SelectField(u'Status', coerce=int,
            choices=MatchPlayer.StatusChoices)
    delete = BooleanField(u'Delete')

    def __init__(self, *args, **kwargs):
        kwargs.setdefault('csrf_enabled', False)
        super(MatchPlayerForm, self).__init__(*args, **kwargs)

class MatchPlayerStatusForm(Form):
    s = HiddenField(u'Status')

class Match(db.Model):
    __tablename__ = 'matches'

    id = db.Column('match_id', db.Integer(unsigned=True), primary_key=True,
            autoincrement=True, nullable=False)
    team_id = db.Column('team_id', db.Integer(unsigned=True),
            db.ForeignKey('teams.team_id'), index=True, nullable=False)
    opponent_id = db.Column('opponent_id', db.Integer(unsigned=True),
            db.ForeignKey('opponents.opponent_id'), index=True, nullable=True)
    competition_id = db.Column('competition_id', db.Integer(unsigned=True),
            db.ForeignKey('competitions.competition_id'),
            index=True, nullable=False)
    server_id = db.Column('server_id', db.Integer(unsigned=True),
            db.ForeignKey('servers.server_id'), index=True, nullable=False)
    size = db.Column('size', db.Integer(unsigned=True), nullable=False)
    date = db.Column('date', db.DateTime, nullable=False)
    password = db.Column('password', db.String(255), nullable=False)
    comments = db.Column('comments', db.String(255), nullable=False)
    date_created = db.Column('date_created', db.DateTime, nullable=False)
    creator_user_id = db.Column('creator_user_id', id_type, 
            db.ForeignKey('users.user_id'),
            nullable=False)
    forum_post_url = db.Column('forum_post_url', db.String(255),
            nullable=True)

    user = db.relation("User")
    team = db.relation("Team", primaryjoin="Team.id == Match.team_id")
    opponent = db.relation("Opponent",
            primaryjoin="Opponent.id == Match.opponent_id")
    competition = db.relation("Competition")
    server = db.relation("Server")

    players = db.relation("MatchPlayer",
            order_by="MatchPlayer.status.asc(), MatchPlayer.date_updated.asc()",
            cascade="delete", lazy='dynamic')

    posts = db.relation("ForumBotQueuedPost",
            cascade="delete")

    def __init__(self, **kwargs):
        kwargs.setdefault('team_id', None)
        kwargs.setdefault('opponent_id', None)
        kwargs.setdefault('competition_id', None)
        kwargs.setdefault('server_id', None)
        kwargs.setdefault('size', 4)
        kwargs.setdefault('date_created', datetime.utcnow())
        kwargs.setdefault('password', '')
        kwargs.setdefault('comments', '')

        self.team_id = kwargs['team_id']
        self.creator_user_id = kwargs['creator_user_id']
        self.opponent_id = kwargs['opponent_id']
        self.competition_id = kwargs['competition_id']
        self.server_id = kwargs['server_id']
        self.size = kwargs['size']
        self.date = kwargs['date']
        self.password = kwargs['password']
        self.comments = kwargs['comments']
        self.date_created = kwargs['date_created']

class MatchForm(Form):
    team_id = SelectField(u'Team', coerce=int, validators=[Required()])
    opponent_id = SelectField(u'Opponent', coerce=int, choices=[],
            validators=[Required()])
    competition_id = SelectField(u'Competition', coerce=int, 
            validators=[Required()])
    server_id = SelectField(u'Server', coerce=int, validators=[Required()])
    date = MatchDateTimeField(u'Date', validators=[Required()])
    #size = HiddenIntegerField(u'Size', default=6, \
    #        validators=[NumberRange(min=0,max=100), Required()])
    password = TextField(u'Server Password', \
            validators=[Length(min=0,max=100), Optional()])
    comments = TextAreaField(u'Comments', validators=[Optional()])

    players = FieldList(FormField(MatchPlayerForm))

class MatchMap(db.Model):
    __tablename__ = 'match_maps'
    match_id = db.Column('match_id', id_type, \
            db.ForeignKey('matches.match_id'), nullable=False, primary_key=True)
    order = db.Column('order', db.Integer(unsigned=True), nullable=False, \
            primary_key=True, autoincrement=False)
    map_id = db.Column('map_id', id_type, db.ForeignKey('maps.map_id'), \
            nullable=False)
    side_id = db.Column('side_id', id_type, db.ForeignKey('sides.side_id'), \
            nullable=False)
    gametype_id = db.Column('gametype_id', id_type, \
            db.ForeignKey('gametypes.gametype_id'), nullable=False)

