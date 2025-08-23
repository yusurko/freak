
from __future__ import annotations

from quart import Blueprint, abort, flash, redirect, render_template, request
from quart_auth import current_user, login_required
from sqlalchemy import delete, select

from freak import UserLoader


from ..models import Post, db, User
current_user: UserLoader

bp = Blueprint('delete', __name__)


@bp.route('/delete/post/<b32l:id>', methods=['GET', 'POST'])
@login_required
async def delete_post(id: int):
    async with db as session:
        p = (await session.execute(select(Post).where(Post.id == id, Post.author_id == current_user.id))).scalar()
    
        if p is None:
            abort(404)
        if p.author != current_user.user:
            abort(403)

        pt = p.topic_or_user()
        
        if request.method == 'POST':
            session.execute(delete(Post).where(Post.id == id, Post.author_id == current_user.id))
            await flash('Your post has been deleted')
            return redirect(pt.url()), 303
    
    return await render_template('singledelete.html', p=p)