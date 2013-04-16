from tardyrush import db

from flask.ext.wtf import Form, TextField, IntegerField, DateTimeField, \
        TextAreaField, HiddenField, SelectField, FormField, FieldList, \
        BooleanField, Length, NumberRange, Optional, Required, widgets, \
        ValidationError

from helpers import *
from inputs import *
from fields import *

from matches import *
from users import *

class Team(db.Model):
    __tablename__ = 'teams'
    id = create_id_column('team')
    name = create_name_column('team')
    tag = db.Column('tag', db.String(255), nullable=False)
    url = db.Column('url', db.String(255), nullable=True)
    join_password = db.Column('join_password', db.String(255), nullable=False)
    time_zone = db.Column('time_zone', db.String(255), nullable=False,
                          server_default='US/Eastern')
    date_created = db.Column('date_created', db.DateTime, nullable=False)

    players = db.relation('TeamPlayer',
                          order_by='TeamPlayer.status.asc()',
                          lazy='dynamic',
                          cascade="delete")
    matches = db.relation(Match,
                          primaryjoin=Match.team_id == id,
                          cascade="delete")
    opponents = db.relation('Opponent', lazy='dynamic', cascade='delete')
    servers = db.relation('Server', cascade='delete')

    posts = db.relation("ForumBotQueuedPost", cascade="delete")

    forum_bots = db.relation("ForumBot", cascade="delete")

class TeamPlayer(db.Model):
    __tablename__ = 'team_players'
    team_id = db.Column('team_id', id_type, db.ForeignKey('teams.team_id'),
            nullable=False, primary_key=True)
    user_id = db.Column('user_id', id_type, db.ForeignKey('users.user_id'),
            nullable=False, primary_key=True)

    user = db.relation(User)
    team = db.relation(Team,
            order_by=Team.name.asc())

    date_joined = db.Column('date_joined', db.DateTime, nullable=False)

    StatusFounder = 10
    StatusLeader = 20
    StatusNormal = 30

    status = db.Column('status', db.Integer, nullable=False,
            server_default='0')

    StatusPrettyNames = { StatusNormal: "Normal",
                          StatusFounder: "Founder",
                          StatusLeader: "Leader" }

    StatusChoices = [ (StatusNormal, "Normal"),
                      (StatusFounder, "Founder"),
                      (StatusLeader, "Leader") ]

    def __init__(self, **kwargs):
        kwargs.setdefault('team_id', 0)
        kwargs.setdefault('user_id', 0)
        kwargs.setdefault('status', self.StatusNormal)
        kwargs.setdefault('date_joined', datetime.utcnow())

        self.date_joined = kwargs['date_joined']
        self.team_id = kwargs['team_id']
        self.user_id = kwargs['user_id']
        self.status = kwargs['status']

    @property
    def pretty_status(self):
        return self.__class__.StatusPrettyNames.get(self.status, "")

    def is_team_leader(self):
        return self.status in (self.StatusLeader, self.StatusFounder)

    def is_founder(self):
        return self.status == self.StatusFounder

class TeamPlayerForm(Form):
    user_id = HiddenIntegerField(u'User ID', validators=[NumberRange(min=1),
            Required()])
    status = SelectField(u'Status', coerce=int,
            choices=TeamPlayer.StatusChoices)
    delete = BooleanField(u'Delete')

    def __init__(self, *args, **kwargs):
        kwargs.setdefault('csrf_enabled', False)
        super(TeamPlayerForm, self).__init__(*args, **kwargs)

class TeamForm(Form):
    name = StrippedTextField(u'Team Name', \
            validators=[Unique(), Length(min=0,max=100), Required()])
    tag = StrippedTextField(u'Tag', \
            validators=[Length(min=0,max=20), Required()])
    url = StrippedTextField(u'Web Site', \
            validators=[Length(min=0,max=255), Optional()])
    join_password = TextField(u'Join Password', \
            validators=[Length(min=0,max=255), Optional()])
    time_zone = SelectField(u'Team Time Zone', default="US/Eastern", \
            choices=User.TimeZoneChoices,\
            validators=[Required()])

class TeamPlayersForm(Form):
    players = FieldList(FormField(TeamPlayerForm))

class JoinTeamForm(Form):
    password = TextField(u'Password', validators=[Required()])

    def validate_password(form, field):
        pass

class LeaveTeamForm(Form):
    pass

class PlayerStatsCombineForm(Form):
    game = SelectField(u'Game', coerce=int)
    competition = SelectField(u'Competition', coerce=int)
    gametype = SelectField(u'Game Type', coerce=int)
    map = SelectField(u'Map', coerce=int)
