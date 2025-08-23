

from __future__ import annotations
import enum
import logging
import sys
import re
import datetime
from typing import Mapping
from quart import Blueprint, render_template, request, redirect, flash
from quart_auth import AuthUser, login_required, login_user, logout_user, current_user
from suou.functools import deprecated
from werkzeug.exceptions import Forbidden

from .. import UserLoader
from ..models import REPORT_REASONS, db, User
from ..utils import age_and_days, get_request_form
from sqlalchemy import select, insert
from werkzeug.security import generate_password_hash

current_user: UserLoader

logger = logging.getLogger(__name__)

bp = Blueprint('accounts', __name__)

class LoginStatus(enum.Enum):
    SUCCESS = 0
    ERROR = 1
    SUSPENDED = 2
    PASS_EXPIRED = 3

def check_login(user: User | None, password: str) -> LoginStatus:
    try:
        if user is None:
            return LoginStatus.ERROR
        if ('$' not in user.passhash) and user.email:
            return LoginStatus.PASS_EXPIRED
        if not user.is_active:
            return LoginStatus.SUSPENDED
        if user.check_password(password):
            return LoginStatus.SUCCESS
    except Exception as e:
        logger.error(f'{e}')
    return LoginStatus.ERROR


@bp.get('/login')
async def login():
    return await render_template('login.html')

@bp.post('/login')
async def post_login():
    form = await get_request_form()
    # TODO schema validator
    username: str = form['username']
    password: str = form['password']
    if '@' in username:
        user_q = select(User).where(User.email == username)
    else:
        user_q = select(User).where(User.username == username)

    async with db as session:
        user = (await session.execute(user_q)).scalar()

        match check_login(user, password):
            case LoginStatus.SUCCESS:
                remember_for = int(form.get('remember', 0))
                if remember_for > 0:
                    login_user(UserLoader(user.get_id()), remember=True)
                else:
                    login_user(UserLoader(user.get_id()))
                return redirect(request.args.get('next', '/'))
            case LoginStatus.ERROR:
                await flash('Invalid username or password')
            case LoginStatus.SUSPENDED:
                await flash('Your account is suspended')
            case LoginStatus.PASS_EXPIRED:
                await flash('You need to reset your password following the procedure.') 
    return await render_template('login.html')

@bp.route('/logout')
async def logout():
    logout_user()
    await flash('Logged out. Come back soon~')
    return redirect(request.args.get('next','/'))

## XXX temp
@deprecated('no good use')
def _currently_logged_in() -> bool:
    return bool(current_user)


# XXX temp
@deprecated('please implement IpBan table')
def _check_ip_bans(ip) -> bool:
    if ip in ('127.0.0.1', '::1', '::'):
        return True
    return False

async def validate_register_form() -> dict:
    form = await get_request_form()
    f = dict()
    try:
        f['gdpr_birthday'] = datetime.date.fromisoformat(form['birthday'])

        if age_and_days(f['gdpr_birthday']) == (0, 0):
            # block bot attempt to register
            raise Forbidden
        if age_and_days(f['gdpr_birthday']) < (14,):
            f['banned_at'] = datetime.datetime.now()
            f['banned_reason'] = REPORT_REASONS['underage']
        
    except ValueError:
        raise ValueError('Invalid date format')
    f['username'] = form['username'].lower()
    if not re.fullmatch('[a-z0-9_-]+', f['username']):
        raise ValueError('Username can contain only letters, digits, underscores and dashes.')
    f['display_name'] = form.get('full_name')

    if form['password'] != form['confirm_password']:
        raise ValueError('Passwords do not match.')
    f['passhash'] = generate_password_hash(form['password'])

    f['email'] = form['email'] or None

    is_ip_banned: bool = await _check_ip_bans()

    if is_ip_banned:
        raise ValueError('Your IP address is banned.')
        
    if _currently_logged_in() and not form.get('confirm_another'):
        raise ValueError('You are already logged in. Please confirm you want to create another account by checking the option.')
    if not form.get('legal'):
        raise ValueError('You must accept Terms in order to create an account.')

    return f


class RegisterStatus(enum.Enum):
    SUCCESS = 0
    ERROR = 1
    USERNAME_TAKEN = 2
    IP_BANNED = 3
    

@bp.post('/register')
async def register_post():
    try:
        user_data = await validate_register_form()
    except ValueError as e:
        if e.args:
            await flash(e.args[0])
        return await render_template('register.html')

    try:
        async with db as session:
            await session.execute(insert(User).values(**user_data))
        
        await flash('Account created successfully. You can now log in.')
        return redirect(request.args.get('next', '/'))
    except Exception as e:
        sys.excepthook(*sys.exc_info())
        await flash('Unable to create account (possibly your username is already taken)')
    return await render_template('register.html')

@bp.get('/register')
async def register_get():
    return await render_template('register.html')

COLOR_SCHEMES = {'dark': 2, 'light': 1, 'system': 0, 'unset': 0}

@bp.route('/settings', methods=['GET', 'POST'])
@login_required
async def settings():
    if request.method == 'POST':
        form = await get_request_form()
        async with db as session:
            changes = False
            user = current_user.user
            color_scheme = COLOR_SCHEMES[form.get('color_scheme')] if 'color_scheme' in form else None
            color_theme: int = int(form.get('color_theme')) if 'color_theme' in form else None
            biography: str = form.get('biography')
            display_name: str = form.get('display_name')
            
            if display_name and display_name != user.display_name:
                changes, user.display_name = True, display_name.strip()
            if biography and biography != user.biography:
                changes, user.biography = True, biography.strip()
            if color_scheme is not None and color_theme is not None:
                comp_color_theme = 256 * color_scheme + color_theme
                if comp_color_theme != user.color_theme:
                    changes, user.color_theme = True, comp_color_theme
            if changes:
                session.add(user)
                session.commit()
            await flash('Changes saved!')
        
    return await render_template('usersettings.html')

