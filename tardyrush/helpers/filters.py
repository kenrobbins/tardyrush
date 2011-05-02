import re
import pytz
import urllib
import datetime

from babel import dates

from jinja2 import evalcontextfilter, Markup, escape
from flaskext.babel import format_datetime, to_user_timezone

from tardyrush import app
from tardyrush.models import MatchPlayer, CompletedMatch, TeamPlayer, \
        ForumBot
from teams import *

_paragraph_re = re.compile(r'(?:\r\n|\r|\n){2,}')

@app.template_filter('nl2br')
@evalcontextfilter
def nl2br(eval_ctx, value):
    result = u'\n\n'.join(u'<p>%s</p>' % p.replace('\n', '<br/>\n') \
        for p in _paragraph_re.split(escape(value)))
    if eval_ctx.autoescape:
        result = Markup(result)
    return result

@app.template_filter()
def urlencode(url, **kwargs):
    seq = []
    for key, val in kwargs.iteritems():
        if isinstance(val, (list, tuple)):
            for v in val:
                seq.append( (key, v) )
        else:
            seq.append( (key, val) )
    return "%s?%s" % (url, urllib.urlencode(seq))

@app.template_filter()
def urlquote(s, safe=''):
    return urllib.quote(s, safe)

@app.template_filter()
def is_forfeit(val):
    return val == CompletedMatch.FinalResultByForfeit

@app.template_filter()
def server_copy_text(fmt, m):
    fmt = fmt.replace("%ADDR%", m.server.address)
    fmt = fmt.replace("%PW%", m.password)
    return fmt

@app.template_filter()
def add_time(dt, **kwargs):
    return dt + datetime.timedelta(**kwargs)

@app.template_filter()
def kdr(fmt, kills, deaths):
    if deaths == 0:
        return '<span class="inf_kdr">&#8734;</span>'
    kdr = float(kills) / float(deaths)
    return fmt % kdr

@app.template_filter()
def pretty_forum_bot_type(value):
    return ForumBot.TypePrettyNames[value] 

@app.template_filter()
def pretty_team_player_status(value):
    return TeamPlayer.StatusPrettyNames[value] 

@app.template_filter()
def pretty_match_player_status(value):
    return MatchPlayer.StatusPrettyNames[value] 

@app.template_filter()
def can_edit_match(team_id=None):
    return is_team_leader(team_id)

@app.template_filter()
def can_edit_team(team_id=None):
    return is_team_leader(team_id)

@app.template_filter()
def user_time_zone(fmt=None):
    if not fmt:
        fmt = 'zzzz'
    return format_datetime(to_user_timezone(datetime.datetime.utcnow()),
            fmt)

@app.template_filter()
def match_last_updated_format(value):
    return format_datetime(value, "MMM d 'at' h':'mm a")

@app.template_filter()
def matches_datetime_format(value):
    # show the year if the value's year is not the current year, but only do
    # that if it's more than 45 days in the future.  that way, at end of the
    # year, it doesn't show the year for everything.
    utcnow = datetime.datetime.utcnow()
    if value.year != utcnow.year:
        return format_datetime(value, "MMM d',' yyyy 'at' h':'mm a zzz")

    return format_datetime(value, "EEE',' MMM d 'at' h':'mm a zzz")

@app.template_filter()
def matches_date_format(value):
    return format_datetime(value, "MMMM d',' yyyy")

@app.template_filter()
def matches_time_format(value):
    return format_datetime(value, "h':'mm a zzz")

@app.template_filter()
def matches_datetime_format_full(value):
    return format_datetime(value, "EEEE',' MMMM d',' yyyy 'at' h':'mm a zzz")

def matches_datetime_format_full_for_team(dt, tz):
    return dates.format_datetime(dt,
            "EEEE',' MMMM d',' yyyy 'at' h':'mm a zzz",
            locale='en_US',
            tzinfo=pytz.timezone(tz))

def matches_datetime_format_for_team(value, tz):
    utcnow = datetime.datetime.utcnow()
    if value.year != utcnow.year:
        return dates.format_datetime(value,
                "MMM d',' yyyy 'at' h':'mm a zzz",
                locale='en_US',
                tzinfo=pytz.timezone(tz))

    return dates.format_datetime(value,
            "EEE',' MMM d 'at' h':'mm a zzz",
            locale='en_US',
            tzinfo=pytz.timezone(tz))

