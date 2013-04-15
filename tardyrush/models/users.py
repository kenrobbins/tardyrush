from tardyrush import db

from fields import StrippedTextField
from validators import Unique
from datetime import datetime

from pytz import common_timezones

from flask.ext.wtf import Form, TextField, IntegerField, DateTimeField, \
        TextAreaField, HiddenField, SelectField, FormField, FieldList, \
        BooleanField, Length, NumberRange, Optional, Required

class User(db.Model):
    __tablename__ = 'users'

    TimeZoneChoices = [ (tz, unicode(tz)) for tz in common_timezones ]

    id = db.Column('user_id', db.Integer(unsigned=True), primary_key=True, \
            autoincrement=True, nullable=False)
    openid = db.Column('openid', db.String(255), unique=True, nullable=False)
    name = db.Column('username', db.String(255), unique=True, nullable=False)
    email = db.Column('email', db.String(255), unique=True, nullable=False)
    time_zone = db.Column('time_zone', db.String(255), nullable=False,
            server_default='US/Eastern')
    email_settings = db.Column('email_settings', db.Integer(unsigned=True),
            nullable=False, server_default='0')
    date_joined = db.Column('date_joined', db.DateTime, nullable=False)

    team_statuses = db.relation("TeamPlayer", cascade="delete")

    # email settings
    EmailNone = 1
    EmailMatchAdded = 2

    EmailSettings = ( EmailNone, EmailMatchAdded )
    EmailSettingsChoices = [ (EmailNone, "No emails"),
                             (EmailMatchAdded,
                                 "Send an email when a new match is added") ]

    def __init__(self, *args, **kwargs):
        kwargs.setdefault('id', 0)
        kwargs.setdefault('name', 'guest')
        kwargs.setdefault('date_joined', datetime.utcnow())
        kwargs.setdefault('time_zone', "US/Eastern")
        kwargs.setdefault('email_settings', self.EmailNone)
        kwargs.setdefault('team_statuses', [])

        self.date_joined = kwargs.get('date_joined')
        self.id = kwargs.get('id')
        self.name = kwargs.get('name')
        self.email = kwargs.get('email')
        self.openid = kwargs.get('openid')
        self.time_zone = kwargs.get('time_zone')
        self.email_settings = kwargs.get('email_settings')
        self.team_statuses = kwargs.get('team_statuses')

    @property
    def is_guest(self):
        return self.id == 0

    @property
    def founder_teams(self):
        ft = []
        for t in self.team_statuses:
            if t.is_founder():
                ft.append(t.team_id)
        return ft

    @property
    def team_leader_teams(self):
        return [t.team_id for t in self.team_statuses if t.is_team_leader()]

    @property
    def teams(self):
        tdict = {}
        for t in self.team_statuses:
            tdict[t.team_id] = t.team
        return tdict

    @property
    def one_team(self):
        if len(self.teams):
            return self.teams.values()[0]
        return None

    def is_on_team(self, team_id=None):
        if team_id is None:
            return len(self.team_statuses)
        ids = [ t.team_id for t in self.team_statuses ]
        return team_id in ids

    def is_founder(self, team_id=None):
        if team_id is None:
            return len(self.founder_teams) > 0
        return team_id in self.founder_teams

    def is_team_leader(self, team_id=None):
        if team_id is None:
            return self.is_admin()
        return team_id in self.team_leader_teams

    def is_admin(self):
        return len(self.team_leader_teams) > 0

    def can_edit_team(self, team_id=None):
        return self.is_team_leader(team_id)

    def can_edit_match(self, team_id=None):
        return self.is_team_leader(team_id)

    @classmethod
    def create_guest_user(cls):
        return cls()


class UserForm(Form):
    name = StrippedTextField(u'User Name', \
            validators=[Unique(), Length(min=0,max=100), Required()])
    email = StrippedTextField(u'Email', \
            validators=[Unique(), Length(min=0,max=100), Required()])
    next = HiddenField()

class UserSettingsForm(Form):
    email = StrippedTextField(u'Email', \
            validators=[Unique(), Length(min=0,max=100), Required()])
    time_zone = SelectField(u'Time Zone', default="US/Eastern", \
            choices=User.TimeZoneChoices,\
            validators=[Required()])
    email_settings = SelectField(u'Email Settings', default=User.EmailMatchAdded,
            choices=User.EmailSettingsChoices, coerce=int,
            validators=[Required()])

class UserTimeZoneForm(Form):
    time_zone = SelectField(u'Time Zone', default="US/Eastern", \
            choices=User.TimeZoneChoices,\
            validators=[Required()])

