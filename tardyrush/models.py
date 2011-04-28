from tardyrush import app, db
from datetime import datetime, timedelta
from flaskext.wtf import Form, TextField, IntegerField, DateTimeField, \
        TextAreaField, HiddenField, SelectField, FormField, FieldList, \
        BooleanField
from wtforms.widgets import Input
from flaskext.wtf import Length, NumberRange, Optional, Required, widgets, \
        ValidationError
from pytz import common_timezones

import time


class Unique(object):
    def __init__(self, ignore_case=True, values=set()):
        self.ignore_case = ignore_case
        self.values = values

    def __call__(self, form, field):
        if field.data is not None:
            data = field.data.lower() if self.ignore_case else field.data
            if data in self.values:
                raise ValidationError(u'This %s is taken.' % field.name)



class MatchDateTimeInput(Input):
    MonthOptions = [ 
            ( 1, u'January'),
            ( 2, u'February'),
            ( 3, u'March'),
            ( 4, u'April'),
            ( 5, u'May'),
            ( 6, u'June'),
            ( 7, u'July'),
            ( 8, u'August'),
            ( 9, u'September'),
            (10, u'October'),
            (11, u'November'),
            (12, u'December') ]
    DayOptions = [ (i, unicode(i)) for i in range(1,32) ]
    HourOptions = [ (i, unicode(i)) for i in range(1,13) ]
    MinuteOptions = [ (i, "%02d" % i) for i in (0, 15, 30, 45) ]
    AmpmOptions = [ ('am', 'am'), ('pm', 'pm') ]

    def __init__(self, *args, **kwargs):
        super(MatchDateTimeInput, self).__init__(*args, **kwargs)

    def __call__(self, field, **kwargs):
        if not field.data:
            field.data = datetime.utcnow() + timedelta(hours=1)

        html = []

        html.append( "<input class='date' name='%s' size='9' " % field.name )
        html.append( " maxlength='10' value='%02d/%02d/%s' />" % (field.data.month,
            field.data.day, field.data.year) )

        html.append("<span class='matchdate_between'></span>")

        html.append( "<select name='%s'>" % field.name )
        for (val, text) in self.HourOptions:
            if val == field.data.hour or val == (field.data.hour - 12):
                sel = "selected='selected'"
            else:
                sel = ''
            html.append( "<option %s value='h%s'>%s</option>" % (sel, val, text) )
        html.append("</select>")

        html.append( "<select name='%s'>" % field.name )
        for (val, text) in self.MinuteOptions:
            if val == field.data.minute:
                sel = "selected='selected'"
            else:
                sel = ''
            html.append( "<option %s value='m%s'>%s</option>" % (sel, val, text) )
        html.append("</select>")

        html.append( "<select name='%s'>" % field.name )
        for (val, text) in self.AmpmOptions:
            if val == 'pm' and field.data.hour >= 12:
                sel = "selected='selected'"
            else:
                sel = ''
            html.append( "<option %s value='%s'>%s</option>" % (sel, val, text) )
        html.append("</select>")

        return u''.join(html)

class StrippedTextField(TextField):
    def __init__(self, *args, **kwargs):
        super(StrippedTextField, self).__init__(*args, **kwargs)

    def process_formdata(self, valuelist):
        super(StrippedTextField, self).process_formdata(valuelist)
        self.data = self.data.strip() or None

class MatchDateTimeField(DateTimeField):
    widget = MatchDateTimeInput()

    def __init__(self, *args, **kwargs):
        super(MatchDateTimeField, self).__init__(*args, **kwargs)

    def process_formdata(self, valuelist):
        if valuelist:
            ok = 0
            month = None
            day = None
            year = None
            hour = None
            minute = None
            ispm = None
            for v in valuelist:
                if len(v) == 0: continue
                if v[0] == 'h':
                    hour = int(v[1:])
                    ok += 1
                elif v[0] == 'm':
                    minute = int(v[1:])
                    ok += 1
                elif v == 'am':
                    ispm = False
                    ok += 1
                elif v == 'pm':
                    ispm = True
                    ok += 1
                elif len(v) == 10:
                    ok += 3
                    month, day, year = v.split('/')
                    month = int(month)
                    day = int(day)
                    year = int(year)

            if ok == 6:
                if ispm and hour < 12:
                    hour += 12
                elif not ispm and hour == 12:
                    hour = 0

                date_str = "%04s-%02d-%02d %02d:%02d:00" % \
                        (year, month, day, hour, minute)

                try:
                    timetuple = time.strptime(date_str, self.format)
                    self.data = datetime(*timetuple[:6])
                except ValueError:
                    # TODO: change it from none so that the form can display
                    # the partial data
                    self.data = None
                    raise


id_type = db.Integer(unsigned=True)
def create_id_column(name):
    return db.Column(name + '_id', id_type, primary_key=True, \
            autoincrement=True, nullable=False)

def create_name_column(name,unique=True):
    return db.Column(name+'_name', db.String(255), nullable=False,
            unique=unique)

class HiddenIntegerField(IntegerField):
    widget = widgets.HiddenInput()

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

    teams = db.relation("TeamPlayer",
            cascade="delete")

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
    abbr = db.Column('abbreviation', db.String(255), nullable=False, unique=True)
    thumbnail_url = db.Column('thumbnail_column', db.String(255), nullable=False)
    server_copy_format = db.Column('server_copy_format', db.String(255),
            nullable=True)

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
            lazy='dynamic', cascade="delete")
    matches = db.relation(Match,
            primaryjoin=Match.team_id == id, cascade="delete")
    opponents = db.relation('Opponent',
            lazy='dynamic', cascade='delete')
    servers = db.relation('Server', 
            cascade='delete')

    posts = db.relation("ForumBotQueuedPost",
            cascade="delete")

    forum_bots = db.relation("ForumBot",
            cascade="delete")

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

    def is_team_leader(self):
        return self.status == self.StatusLeader or \
                self.status == self.StatusFounder

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






class ContactForm(Form):
    email = StrippedTextField(u'Email', \
            validators=[Length(min=0,max=100), Required()])
    subject = StrippedTextField(u'Subject', \
            validators=[Length(min=0,max=100), Required()])
    comments = TextAreaField(u'Comments', validators=[Required()])








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

class CompletedMatch(db.Model):
    __tablename__ = 'completed_matches'

    id = create_id_column('cmatch')
    team_id = db.Column('team_id', db.Integer(unsigned=True),
            db.ForeignKey('teams.team_id'), index=True, nullable=False)
    opponent_id = db.Column('opponent_id', db.Integer(unsigned=True),
            db.ForeignKey('opponents.opponent_id'), index=True, nullable=True)
    match_id = db.Column('match_id', db.Integer(unsigned=True),
            db.ForeignKey('matches.match_id'), index=True, nullable=True)
    competition_id = db.Column('competition_id', db.Integer(unsigned=True),
            db.ForeignKey('competitions.competition_id'),
            index=True, nullable=False)
    server_id = db.Column('server_id', db.Integer(unsigned=True),
            db.ForeignKey('servers.server_id'), index=True, nullable=False)
    comments = db.Column('comments', db.String(255), nullable=False)
    date_played = db.Column('date_played', db.DateTime, nullable=False,
            index=True, default=datetime.utcnow())
    date_created = db.Column('date_created', db.DateTime, nullable=False,
            default=datetime.utcnow())
    creator_user_id = db.Column('creator_user_id', id_type, 
            db.ForeignKey('users.user_id'),
            nullable=False)
    final_result_method = db.Column('final_result_method', db.Integer(),
            nullable=False)
    
    wins = db.Column('wins', db.Integer(), nullable=False)
    losses = db.Column('losses', db.Integer(), nullable=False)
    draws = db.Column('draws', db.Integer(), nullable=False)

    FinalResultByScore = 1
    FinalResultByRound = 2
    FinalResultByForfeit = 3

    FinalResultChoices = [ (FinalResultByScore, "By Score"),
                           (FinalResultByRound, "By Round") ]

    user = db.relation("User")
    team = db.relation("Team", primaryjoin="Team.id == CompletedMatch.team_id")
    opponent = db.relation("Opponent",
            primaryjoin="Opponent.id == CompletedMatch.opponent_id")
    competition = db.relation("Competition")
    server = db.relation("Server")

    avail_match = db.relation("Match", 
            backref="results", lazy='dynamic')

    rounds = db.relation("CompletedMatchRound",
            cascade="delete,delete-orphan,save-update,merge", lazy='dynamic')

class CompletedMatchRound(db.Model):
    __tablename__ = 'completed_match_rounds'

    cmatch_id = db.Column('cmatch_id', id_type,
            db.ForeignKey('completed_matches.cmatch_id'), 
            nullable=False, primary_key=True, autoincrement=False)
    round_id = db.Column('round_id', db.Integer(unsigned=True), nullable=False,
            primary_key=True, autoincrement=False)
    map_id = db.Column('map_id', id_type, db.ForeignKey('maps.map_id'), \
            nullable=False)
    side_id = db.Column('side_id', id_type, db.ForeignKey('sides.side_id'), \
            nullable=False)
    gametype_id = db.Column('gametype_id', id_type, \
            db.ForeignKey('gametypes.gametype_id'), nullable=False)

    wins = db.Column('wins', db.Integer(), nullable=False)
    losses = db.Column('losses', db.Integer(), nullable=False)
    draws = db.Column('draws', db.Integer(), nullable=False)

    map = db.relation(Map)
    side = db.relation(Side)
    gametype = db.relation(GameType)

    players = db.relation("CompletedMatchPlayer", # TODO order by name?
            cascade="delete,delete-orphan,save-update,merge")#, lazy='dynamic')

class CompletedMatchPlayer(db.Model):
    __tablename__ = 'completed_match_players'

    cmatch_id = db.Column('cmatch_id', db.Integer(unsigned=True), \
            nullable=False, primary_key=True)
    round_id = db.Column('round_id', db.Integer(unsigned=True),
            primary_key=True)
    user_id = db.Column('user_id', db.Integer(unsigned=True), \
            db.ForeignKey('users.user_id'), nullable=False, primary_key=True)

    __table_args__ = ( db.ForeignKeyConstraint(['cmatch_id', 'round_id'],
            ['completed_match_rounds.cmatch_id', 
                'completed_match_rounds.round_id']), {} )

    kills = db.Column('kills', db.Integer(unsigned=True), nullable=False)
    deaths = db.Column('deaths', db.Integer(unsigned=True), nullable=False)
    off_objs = db.Column('offensive_objectives', db.Integer(unsigned=True),
            nullable=False)
    def_objs = db.Column('defensive_objectives', db.Integer(unsigned=True),
            nullable=False)

    user = db.relation("User")
  


class CompletedMatchPlayerForm(Form):
    user_id = SelectField(u'Player', coerce=int, choices=[], 
            validators=[Required()])
    kills = IntegerField(u'Kills', default=0,
            validators=[NumberRange(min=0)])
    deaths = IntegerField(u'Deaths', default=0,
            validators=[NumberRange(min=0)])
    off_objs = IntegerField(u'Offensive Objectives', default=0,
            validators=[NumberRange(min=0)])
    def_objs = IntegerField(u'Defensive Objectives', default=0,
            validators=[NumberRange(min=0)])


    def __init__(self, *args, **kwargs):
        kwargs.setdefault('csrf_enabled', False)
        super(CompletedMatchPlayerForm, self).__init__(*args, **kwargs)


class CompletedMatchRoundForm(Form):
    map_id = SelectField(u'Map', coerce=int, validators=[Required()],
            choices=[])
    side_id = SelectField(u'Side', coerce=int, validators=[Required()],
            choices=[])
    gametype_id = SelectField(u'Gametype', coerce=int, validators=[Required()],
            choices=[])

    wins = IntegerField(u'Wins', validators=[NumberRange(min=0)], default=0)
    losses = IntegerField(u'Losses', validators=[NumberRange(min=0)], default=0)
    draws = IntegerField(u'Draws', validators=[NumberRange(min=0)], default=0)

    players = FieldList(FormField(CompletedMatchPlayerForm))

    def __init__(self, *args, **kwargs):
        kwargs.setdefault('csrf_enabled', False)
        super(CompletedMatchRoundForm, self).__init__(*args, **kwargs)

class CompletedMatchForm(Form):
    team_id = SelectField(u'Team', coerce=int, validators=[Required()])
    match_id = HiddenIntegerField(u'Corresponding Match',
            validators=[NumberRange(min=1), Required()])
    #match_id = SelectField(u'Corresponding Match', choices=[],
    #        coerce=int, validators=[Required()])
    opponent_id = SelectField(u'Opponent', coerce=int, choices=[],
            validators=[Required()])
    competition_id = SelectField(u'Competition', coerce=int, 
            validators=[Required()])
    server_id = SelectField(u'Server', coerce=int, validators=[Required()])
    date_played = MatchDateTimeField(u'Date', validators=[Required()])
    comments = TextAreaField(u'Comments', validators=[Optional()])

    final_result_method = SelectField(u'Final Result', coerce=int,
            validators=[Required()], choices=CompletedMatch.FinalResultChoices)

    rounds = FieldList(FormField(CompletedMatchRoundForm))

