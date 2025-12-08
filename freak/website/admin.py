

import datetime
from functools import wraps
import os
from typing import Callable
import warnings
from quart import Blueprint, abort, redirect, render_template, request, send_from_directory, url_for
from quart_auth import current_user
from markupsafe import Markup
from sqlalchemy import insert, select, update
from suou import additem, not_implemented
import logging

logger = logging.getLogger(__name__)

from freak import UserLoader
from freak.utils import get_request_form

from ..models import REPORT_REASON_STRINGS, REPORT_REASONS, REPORT_TARGET_COMMENT, REPORT_TARGET_POST, REPORT_UPDATE_COMPLETE, REPORT_UPDATE_ON_HOLD, REPORT_UPDATE_REJECTED, Comment, Post, PostReport, User, UserStrike, db

bp = Blueprint('admin', __name__)

current_user: UserLoader

## TODO make admin interface

def admin_required(func: Callable):
    @wraps(func)
    async def wrapper(*a, **ka):
        user: User = current_user.user
        if not user or not user.is_administrator:
            abort(403)
        return await func(*a, **ka)
    return wrapper


TARGET_TYPES = {
    Post: REPORT_TARGET_POST,
    Comment: REPORT_TARGET_COMMENT
}

def account_status_string(u: User):
    if u.is_active:
        return 'Active'
    elif u.banned_at:
        s = 'Suspended'
        if u.banned_until:
            s += f' (until {u.banned_until:%b %d, %Y %H:%M})'
        if u.banned_reason in REPORT_REASON_STRINGS:
            s += f' ({REPORT_REASON_STRINGS[u.banned_reason]})'
        return s
    elif u.is_disabled_by_user:
        return 'Paused'
    else:
        return 'Inactive'

def colorized_account_status_string(u: User):
    textc = account_status_string(u)
    t1, t2, t3 = textc.partition('(')
    if u.is_active:
        base = '<span class="success">{0}</span>'
    elif u.banned_at:
        base = '<span class="error">{0}</span>'
    else:
        base = '<span class="warning">{0}</span>'
    if t2:
        base += ' <span class="faint">{1}</span>'
    return Markup(base).format(t1, t2 + t3)

async def remove_content(target, reason_code: int):
    async with db as session:
        if isinstance(target, Post):
            target.removed_at = datetime.datetime.now()
            target.removed_by_id = current_user.id
            target.removed_reason = reason_code
        elif isinstance(target, Comment):
            target.removed_at = datetime.datetime.now()
            target.removed_by_id = current_user.id
            target.removed_reason = reason_code
        session.add(target)

def get_author(target) -> User | None:
    if isinstance(target, (Post, Comment)):
        return target.author
    return None

def get_content(target) -> str | None:
    if isinstance(target, Post):
        return target.title + '\n\n' + target.text_content
    elif isinstance(target, Comment):
        return target.text_content
    return None

## REPORT ACTIONS ##

REPORT_ACTIONS = {}

@additem(REPORT_ACTIONS, '1')
async def accept_report(target, source: PostReport):
    async with db as session:
        if source.is_critical():
            warnings.warn('attempted remove on a critical report case, striking instead', UserWarning)
            return await strike_report(target, source)

        await remove_content(target, source.reason_code)

        source.update_status = REPORT_UPDATE_COMPLETE
        # XXX disabled because of a session conflict
        #session.add(source)


@additem(REPORT_ACTIONS, '2')
async def strike_report(target, source: PostReport):
    async with db as session:
        await remove_content(target, source.reason_code)

        author = get_author(target)
        if author:
            session.execute(insert(UserStrike).values(
                user_id = author.id,
                target_type = TARGET_TYPES[type(target)],
                target_id = target.id,
                target_content = get_content(target),
                reason_code = source.reason_code,
                issued_by_id = current_user.id
            ))

            if source.is_critical():
                author.banned_at = datetime.datetime.now()
                author.banned_reason = source.reason_code

        source.update_status = REPORT_UPDATE_COMPLETE
        #session.add(source)


@additem(REPORT_ACTIONS, '0')
async def reject_report(target, source: PostReport):
    async with db as session:
        source.update_status = REPORT_UPDATE_REJECTED
        #session.add(source)


@additem(REPORT_ACTIONS, '3')
async def withhold_report(target, source: PostReport):
    async with db as session:
        source.update_status = REPORT_UPDATE_ON_HOLD
        #session.add(source)


@additem(REPORT_ACTIONS, '4')
@not_implemented()
def escalate_report(target, source: PostReport):
    ...

## END report actions

@bp.route('/admin/')
@admin_required
async def homepage():
    return await render_template('admin/admin_home.html')

@bp.route('/admin/style.css')
async def style_css():
    return redirect('/static/admin/style.css'), 303

@bp.route('/admin/reports/')
@admin_required
async def reports():
    report_list = await db.paginate(select(PostReport).order_by(PostReport.id.desc()))
    return await render_template('admin/admin_reports.html',
    report_list=report_list, report_reasons=REPORT_REASON_STRINGS)

@bp.route('/admin/reports/<b32l:id>', methods=['GET', 'POST'])
@admin_required
async def report_detail(id: int):
    async with db as session:
        report = (await session.execute(select(PostReport).where(PostReport.id == id))).scalar()
        if report is None:
            abort(404)
        target = await report.target()
        if target is None:
            abort(404)
        if request.method == 'POST':
            form = await get_request_form()
            action = REPORT_ACTIONS[form['do']]
            await action(target, report)
            return redirect(url_for('admin.reports'))
    return await render_template('admin/admin_report_detail.html', report=report,
        report_reasons=REPORT_REASON_STRINGS)

@bp.route('/admin/strikes/')
@admin_required
async def strikes():
    strike_list = await db.paginate(select(UserStrike).order_by(UserStrike.id.desc()))
    return await render_template('admin/admin_strikes.html',
    strike_list=strike_list, report_reasons=REPORT_REASON_STRINGS)


@bp.route('/admin/users/')
@admin_required
async def users():
    user_list = await db.paginate(select(User).order_by(User.joined_at.desc()), page=int(request.args.get('page', 1)))
    return await render_template('admin/admin_users.html',
    user_list=user_list, account_status_string=colorized_account_status_string)

@bp.route('/admin/users/<b32l:id>', methods=['GET', 'POST'])
@admin_required
async def user_detail(id: int):
    async with db as session:
        u = (await session.execute(select(User).where(User.id == id))).scalar()
        if u is None:
            abort(404)
        if request.method == 'POST':
            form = await get_request_form()
            action = form['do']
            if action == 'suspend':
                u.banned_at = datetime.datetime.now()
                u.banned_by_id = current_user.id
                u.banned_reason = REPORT_REASONS.get(form.get('reason'), 0)
            elif action == 'unsuspend':
                u.banned_at = None
                u.banned_by_id = None
                u.banned_until = None
                u.banned_reason = None
            elif action == 'to_3d':
                u.banned_at = datetime.datetime.now()
                u.banned_until = datetime.datetime.now() + datetime.timedelta(days=3)
                u.banned_by_id = current_user.id
                u.banned_reason = REPORT_REASONS.get(form.get('reason'), 0)
            else:
                abort(400)
        strikes = (await session.execute(select(UserStrike).where(UserStrike.user_id == id).order_by(UserStrike.id.desc()))).scalars()
    return await render_template('admin/admin_user_detail.html', u=u,
    report_reasons=REPORT_REASON_STRINGS, account_status_string=colorized_account_status_string, strikes=strikes)


