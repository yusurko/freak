

from __future__ import annotations

from quart import Blueprint, render_template, request
from quart_auth import current_user, login_required
from sqlalchemy import insert, select

from freak import UserLoader
from ..models import REPORT_TARGET_COMMENT, REPORT_TARGET_POST, ReportReason, User, post_report_reasons, Comment, Post, PostReport, REPORT_REASONS, db

bp = Blueprint('reports', __name__)

current_user: UserLoader

def description_text(rlist: list[ReportReason], key: str) -> str:
    results = [x.description for x in rlist if x.code == key]
    return results[0] if results else key

@bp.route('/report/post/<b32l:id>', methods=['GET', 'POST'])
@login_required
async def report_post(id: int):
    async with db as session:
        p: Post | None = (await session.execute(select(Post).where(Post.id == id))).scalar()
        if p is None:
            return await render_template('reports/report_404.html', target_type = 1), 404
        if p.author_id == current_user.id:
            return await render_template('reports/report_self.html', back_to_url=p.url()), 403
        if request.method == 'POST':
            reason = request.args['reason']
            await session.execute(insert(PostReport).values(
                author_id = current_user.id,
                target_type = REPORT_TARGET_POST,
                target_id = id,
                reason_code = REPORT_REASONS[reason]
            ))
            session.commit()
            return await render_template('reports/report_done.html', back_to_url=p.url())
    return await render_template('reports/report_post.html', id = id,
        report_reasons = post_report_reasons, description_text=description_text)

@bp.route('/report/comment/<b32l:id>', methods=['GET', 'POST'])
@login_required
async def report_comment(id: int):
    async with db as session:
        c: Comment | None = (await session.execute(select(Comment).where(Comment.id == id))).scalar()
        if c is None:
            return await render_template('reports/report_404.html', target_type = 2), 404
        if c.author_id == current_user.id:
            return await render_template('reports/report_self.html', back_to_url=c.parent_post.url()), 403
        if request.method == 'POST':
            reason = request.args['reason']
            session.execute(insert(PostReport).values(
                author_id = current_user.id,
                target_type = REPORT_TARGET_COMMENT,
                target_id = id,
                reason_code = REPORT_REASONS[reason]
            ))
            session.commit()
            return await render_template('reports/report_done.html', 
                back_to_url=c.parent_post.url())
    return await render_template('reports/report_comment.html', id = id,
        report_reasons = post_report_reasons, description_text=description_text)

