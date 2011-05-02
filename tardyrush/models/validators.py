from flaskext.wtf import ValidationError

class Unique(object):
    def __init__(self, ignore_case=True, values=set()):
        self.ignore_case = ignore_case
        self.values = values

    def __call__(self, form, field):
        if field.data is not None:
            data = field.data.lower() if self.ignore_case else field.data
            if data in self.values:
                raise ValidationError(u'This %s is taken.' % field.name)
