import time

from inputs import *
from flask.ext.wtf import widgets, TextField, IntegerField, DateTimeField,\
        HiddenField

class HiddenIntegerField(IntegerField, HiddenField):
    widget = widgets.HiddenInput()

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
