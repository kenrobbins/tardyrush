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
    steam_id = db.Column('steam_id', db.String(255), unique=True, nullable=True)
    time_zone = db.Column('time_zone', db.String(255), nullable=False,
            server_default='US/Eastern')
    email_settings = db.Column('email_settings', db.Integer(unsigned=True),
            nullable=False, server_default='0')
    date_joined = db.Column('date_joined', db.DateTime, nullable=False)

    teams = db.relation("TeamPlayer", cascade="delete")

    # email settings
    EmailNone = 1
    EmailMatchAdded = 2

    EmailSettings = ( EmailNone, EmailMatchAdded )
    EmailSettingsChoices = [ (EmailNone, "No emails"),
                             (EmailMatchAdded, 
                                 "Send an email when a new match is added") ]

    def __init__(self, **kwargs):
        kwargs.setdefault('date_joined', datetime.utcnow())
        kwargs.setdefault('steam_id', None)
        kwargs.setdefault('time_zone', "US/Eastern")
        kwargs.setdefault('email_settings', self.EmailMatchAdded)

        self.date_joined = kwargs['date_joined']
        self.name = kwargs['name']
        self.email = kwargs['email']
        self.openid = kwargs['openid']
        self.steam_id = kwargs['steam_id']
        self.time_zone = kwargs['time_zone']
        self.email_settings = kwargs['email_settings']

class UserForm(Form):
    name = StrippedTextField(u'User Name', \
            validators=[Unique(), Length(min=0,max=100), Required()])
    email = StrippedTextField(u'Email', \
            validators=[Unique(), Length(min=0,max=100), Required()])
    next = HiddenField()

class UserSettingsForm(Form):
    email = StrippedTextField(u'Email', \
            validators=[Unique(), Length(min=0,max=100), Required()])
    # we kind of get this from the steam openid
    #steam_id = StrippedTextField(u'Steam ID', \
    #        validators=[Unique(), Length(min=0,max=100), Optional()])
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

