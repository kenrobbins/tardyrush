import re
import pytz
import urllib
import datetime
import teams
from babel import dates
from jinja2 import evalcontextfilter, Markup, escape
from flaskext.babel import format_datetime, to_user_timezone
from tardyrush import app
from flask.ext.wtf import HiddenField

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
def add_time(dt, **kwargs):
    return dt + datetime.timedelta(**kwargs)

@app.template_filter()
def kdr(fmt, kills, deaths):
    if deaths == 0:
        return '<span class="inf_kdr">&#8734;</span>'
    kdr = float(kills) / float(deaths)
    return fmt % kdr

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

@app.template_filter()
def record_format(value):
    out = "%d-%d" % (value[0], value[1])
    if value[2]:
        out += "-%d" % (value[2])
    return out

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

@app.template_filter()
def join_none(val, d=u''):
    return d.join(v for v in val if v)

@app.template_filter()
def is_hidden_field(field):
    return isinstance(field, HiddenField)
