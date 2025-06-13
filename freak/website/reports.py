


from flask import Blueprint, render_template, request
from flask_login import current_user, login_required
from ..models import REPORT_TARGET_COMMENT, REPORT_TARGET_POST, ReportReason, post_report_reasons, Comment, Post, PostReport, REPORT_REASONS, db

bp = Blueprint('reports', __name__)

def description_text(rlist: list[ReportReason], key: str) -> str:
    results = [x.description for x in rlist if x.code == key]
    return results[0] if results else key

@bp.route('/report/post/<b32l:id>', methods=['GET', 'POST'])
@login_required
def report_post(id: int):
    p: Post | None = db.session.execute(db.select(Post).where(Post.id == id)).scalar()
    if p is None:
        return render_template('reports/report_404.html', target_type = 1), 404
    if p.author_id == current_user.id:
        return render_template('reports/report_self.html', back_to_url=p.url()), 403
    if request.method == 'POST':
        reason = request.args['reason']
        db.session.execute(db.insert(PostReport).values(
            author_id = current_user.id,
            target_type = REPORT_TARGET_POST,
            target_id = id,
            reason_code = REPORT_REASONS[reason]
        ))
        db.session.commit()
        return render_template('reports/report_done.html', back_to_url=p.url())
    return render_template('reports/report_post.html', id = id,
        report_reasons = post_report_reasons, description_text=description_text)

@bp.route('/report/comment/<b32l:id>', methods=['GET', 'POST'])
@login_required
def report_comment(id: int):
    c: Comment | None = db.session.execute(db.select(Comment).where(Comment.id == id)).scalar()
    if c is None:
        return render_template('reports/report_404.html', target_type = 2), 404
    if c.author_id == current_user.id:
        return render_template('reports/report_self.html', back_to_url=c.parent_post.url()), 403
    if request.method == 'POST':
        reason = request.args['reason']
        db.session.execute(db.insert(PostReport).values(
            author_id = current_user.id,
            target_type = REPORT_TARGET_COMMENT,
            target_id = id,
            reason_code = REPORT_REASONS[reason]
        ))
        db.session.commit()
        return render_template('reports/report_done.html', 
            back_to_url=c.parent_post.url())
    return render_template('reports/report_comment.html', id = id,
        report_reasons = post_report_reasons, description_text=description_text)

