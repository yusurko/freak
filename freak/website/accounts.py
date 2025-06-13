import os, sys
import re
import datetime
from typing import Mapping
from flask import Blueprint, render_template, request, redirect, flash
from flask_login import login_user, logout_user, current_user
from ..models import REPORT_REASONS, db, User
from ..utils import age_and_days
from sqlalchemy import select, insert
from werkzeug.security import generate_password_hash

bp = Blueprint('accounts', __name__)

@bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST' and request.form['username']:
        username = request.form['username']
        password = request.form['password']
        if '@' in username:
            user = db.session.execute(select(User).where(User.email == username)).scalar()
        else:
            user = db.session.execute(select(User).where(User.username == username)).scalar()

        if user and '$' not in user.passhash:
            flash('You need to reset your password following the procedure.') 
            return render_template('login.html')
        elif not user or not user.check_password(password):
            flash('Invalid username or password')
            return render_template('login.html')
        elif not user.is_active:
            flash('Your account is suspended')
        else:
            remember_for = int(request.form.get('remember', 0))
            if remember_for > 0:
                login_user(user, remember=True, duration=datetime.timedelta(days=remember_for))
            else:
                login_user(user)
            return redirect(request.args.get('next', '/'))
    return render_template('login.html')

@bp.route('/logout')
def logout():
    logout_user()
    flash('Logged out. Come back soon~')
    return redirect(request.args.get('next','/'))

## XXX temp
def _currently_logged_in() -> bool:
    return current_user and current_user.is_authenticated

def validate_register_form() -> dict:
    f = dict()
    try:
        f['gdpr_birthday'] = datetime.date.fromisoformat(request.form['birthday'])

        if age_and_days(f['gdpr_birthday']) < (14,):
            f['banned_at'] = datetime.datetime.now()
            f['banned_reason'] = REPORT_REASONS['underage']
    except ValueError:
        raise ValueError('Invalid date format')
    f['username'] = request.form['username'].lower()
    if not re.fullmatch('[a-z0-9_-]+', f['username']):
        raise ValueError('Username can contain only letters, digits, underscores and dashes.')
    f['display_name'] = request.form.get('full_name')

    if request.form['password'] != request.form['confirm_password']:
        raise ValueError('Passwords do not match.')
    f['passhash'] = generate_password_hash(request.form['password'])

    f['email'] = request.form['email'] or None,
        
    if _currently_logged_in() and not request.form.get('confirm_another'):
        raise ValueError('You are already logged in. Please confirm you want to create another account by checking the option.')
    if not request.form.get('legal'):
        raise ValueError('You must accept Terms in order to create an account.')

    return f


@bp.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST' and request.form['username']:
        try:
            user_data = validate_register_form()
        except ValueError as e:
            if e.args:
                flash(e.args[0])
            return render_template('register.html')

        try:
            db.session.execute(insert(User).values(**user_data))

            db.session.commit()
            
            flash('Account created successfully. You can now log in.')
            return redirect(request.args.get('next', '/'))
        except Exception as e:
            sys.excepthook(*sys.exc_info())
            flash('Unable to create account (possibly your username is already taken)')
            return render_template('register.html')

    return render_template('register.html')

