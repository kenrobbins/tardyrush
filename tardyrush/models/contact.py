from flaskext.wtf import Form, TextAreaField, Length, Optional, Required

from fields import StrippedTextField

class ContactForm(Form):
    email = StrippedTextField(u'Email', \
            validators=[Length(min=0,max=100), Required()])
    subject = StrippedTextField(u'Subject', \
            validators=[Length(min=0,max=100), Required()])
    comments = TextAreaField(u'Comments', validators=[Required()])

