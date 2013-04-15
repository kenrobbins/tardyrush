from wtforms.widgets import HTMLString
from datetime import datetime, timedelta

class MatchDateTimeWidget(object):
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
        pass

    def __call__(self, field, **kwargs):
        if not field.data:
            field.data = datetime.utcnow() + timedelta(hours=1)

        class_ = kwargs.get('class', '')
        date_class = kwargs.get('date_class', '')
        time_class = kwargs.get('time_class', '')

        date_class = "%s %s" % (class_, date_class)
        time_class = "%s %s" % (class_, time_class)

        date_class_full = 'class="%s"' % date_class
        time_class_full = 'class="%s"' % time_class

        html = []

        html.append( "<input type='text' id='%s' name='%s' class='date %s'" %
                (field.name, field.name, date_class))
        html.append( " maxlength='10' value='%02d/%02d/%04d' />" % (field.data.month,
            field.data.day, field.data.year) )

        html.append( "<select name='%s' %s>" % (field.name, time_class_full))
        for (val, text) in self.HourOptions:
            if val == field.data.hour or val == (field.data.hour - 12):
                sel = "selected='selected'"
            else:
                sel = ''
            html.append( "<option %s value='h%s'>%s</option>" % (sel, val, text) )
        html.append("</select>")

        html.append( "<select name='%s' %s>" % (field.name, time_class_full))
        for (val, text) in self.MinuteOptions:
            if val == field.data.minute:
                sel = "selected='selected'"
            else:
                sel = ''
            html.append( "<option %s value='m%s'>%s</option>" % (sel, val, text) )
        html.append("</select>")

        html.append( "<select name='%s' %s>" % (field.name, time_class_full))
        for (val, text) in self.AmpmOptions:
            if val == 'pm' and field.data.hour >= 12:
                sel = "selected='selected'"
            else:
                sel = ''
            html.append( "<option %s value='%s'>%s</option>" % (sel, val, text) )
        html.append("</select>")

        return HTMLString(''.join(html))
