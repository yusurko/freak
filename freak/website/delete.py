

from flask import Blueprint, abort, flash, redirect, render_template, request
from flask_login import current_user, login_required
from sqlalchemy import delete, select

from ..models import Post, db


bp = Blueprint('delete', __name__)


@bp.route('/delete/post/<b32l:id>', methods=['GET', 'POST'])
@login_required
def delete_post(id: int):
    p = db.session.execute(select(Post).where(Post.id == id, Post.author == current_user)).scalar()

    if p is None:
        abort(404)
    if p.author != current_user:
        abort(403)

    pt = p.topic_or_user()
    
    if request.method == 'POST':
        db.session.execute(delete(Post).where(Post.id == id, Post.author == current_user))
        db.session.commit()
        flash('Your post has been deleted')
        return redirect(pt.url()), 303
    
    return render_template('singledelete.html', p=p)