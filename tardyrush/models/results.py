from tardyrush import db

from flaskext.wtf import Form, TextField, IntegerField, DateTimeField, \
        TextAreaField, HiddenField, SelectField, FormField, FieldList, \
        BooleanField, Length, NumberRange, Optional, Required

from helpers import *
from inputs import *
from fields import *
from games import *

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
    score = db.Column('score', db.Integer(unsigned=False), nullable=False)

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
    score = IntegerField(u'Score', default=0)

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

