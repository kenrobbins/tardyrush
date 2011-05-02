from wtforms.widgets import Input
from datetime import datetime, timedelta

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
