

import datetime
from functools import wraps
from typing import Callable
from flask import Blueprint, abort, redirect, render_template, request, url_for
from flask_login import current_user
from sqlalchemy import select, update

from ..models import REPORT_REASON_STRINGS, REPORT_UPDATE_COMPLETE, REPORT_UPDATE_ON_HOLD, REPORT_UPDATE_REJECTED, Comment, Post, PostReport, User, db

bp = Blueprint('admin', __name__)

## TODO make admin interface

def admin_required(func: Callable):
    @wraps(func)
    def wrapper(**ka):
        user: User = current_user
        if not user.is_authenticated or not user.is_administrator:
            abort(403)
        return func(**ka)
    return wrapper

def accept_report(target, source: PostReport):
    if isinstance(target, Post):
        target.removed_at = datetime.datetime.now()
        target.removed_by_id = current_user.id
        target.removed_reason = source.reason_code
    elif isinstance(target, Comment):
        target.removed_at = datetime.datetime.now()
        target.removed_by_id = current_user.id
        target.removed_reason = source.reason_code
    db.session.add(target)

    source.update_status = REPORT_UPDATE_COMPLETE
    db.session.add(source)
    db.session.commit()

def reject_report(target, source: PostReport):
    source.update_status = REPORT_UPDATE_REJECTED
    db.session.add(source)
    db.session.commit()

def withhold_report(target, source: PostReport):
    source.update_status = REPORT_UPDATE_ON_HOLD
    db.session.add(source)
    db.session.commit()

REPORT_ACTIONS = {
    '1': accept_report,
    '0': reject_report,
    '2': withhold_report
}

@bp.route('/admin/')
@admin_required
def homepage():
    return render_template('admin/admin_home.html')

@bp.route('/admin/reports/')
@admin_required
def reports():
    report_list = db.paginate(select(PostReport).order_by(PostReport.id.desc()))
    return render_template('admin/admin_reports.html',
    report_list=report_list, report_reasons=REPORT_REASON_STRINGS)

@bp.route('/admin/reports/<b32l:id>', methods=['GET', 'POST'])
@admin_required
def report_detail(id: int):
    report = db.session.execute(select(PostReport).where(PostReport.id == id)).scalar()
    if report is None:
        abort(404)
    if request.method == 'POST':
        action = REPORT_ACTIONS[request.form['do']]
        action(report.target(), report)
        return redirect(url_for('admin.reports'))
    return render_template('admin/admin_report_detail.html', report=report,
        report_reasons=REPORT_REASON_STRINGS)
