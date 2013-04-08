from flask import request, flash, url_for, render_template
from flask import url_for, get_flashed_messages
from flask import redirect as flask_redirect
from flask import jsonify as flask_jsonify

def abs_url_for(*args, **kwargs):
    return "http://tardyrush.com%s" % url_for(*args, **kwargs)

def jsonify(*args, **kwargs):
    kwargs.setdefault('flashes', get_flashed_messages(with_categories=True))
    return flask_jsonify(*args, **kwargs)

def rt(*args, **kwargs):
    if request.values.get('api') == '1':
        csrf = None
        errors = []
        if 'form' in kwargs and kwargs['form']:
            csrf = kwargs['form'].csrf_token.data
            errors = kwargs['form'].errors

        return jsonify(success=False, errors=errors, csrf=csrf)

    kwargs.setdefault('page', {'top':'main', 'sub':''})
    return render_template(*args, **kwargs)

def redirect(*args, **kwargs):
    if request.values.get('api') == '1':
        return jsonify(success=False)
    return flask_redirect(*args, **kwargs)

