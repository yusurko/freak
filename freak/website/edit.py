


import datetime
from quart import Blueprint, abort, flash, redirect, render_template, request
from quart_auth import current_user, login_required
from sqlalchemy import select, update

from freak.utils import get_request_form

from ..models import Post, db

bp = Blueprint('edit', __name__)

@bp.route('/edit/post/<b32l:id>', methods=['GET', 'POST'])
@login_required
async def edit_post(id):
    async with db as session:
        p: Post | None = (await session.execute(select(Post).where(Post.id == id, Post.author == current_user.user))).scalar()

        if p is None:
            abort(404)
        if current_user.id != p.author.id:
            abort(403)

        if request.method == 'POST':
            form = await get_request_form()
            text = form['text']
            privacy = int(form.get('privacy', '0'))

            await session.execute(update(Post).where(Post.id == id).values(
                text_content = text,
                privacy = privacy,
                updated_at = datetime.datetime.now()
            ))
            await session.commit()
            await flash('Your changes have been saved')
            return redirect(p.url()), 303
    return await render_template('edit.html', p=p)

