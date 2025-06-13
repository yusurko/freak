


import datetime
from flask import Blueprint, abort, flash, redirect, render_template, request
from flask_login import current_user, login_required

from ..models import Post, db


bp = Blueprint('edit', __name__)

@bp.route('/edit/post/<b32l:id>', methods=['GET', 'POST'])
@login_required
def edit_post(id):
    p: Post | None = db.session.execute(db.select(Post).where(Post.id == id)).scalar()

    if p is None:
        abort(404)
    if current_user.id != p.author.id:
        abort(403)

    if request.method == 'POST':
        text = request.form['text']
        privacy = int(request.form.get('privacy', '0'))

        db.session.execute(db.update(Post).where(Post.id == id).values(
            text_content = text,
            privacy = privacy,
            updated_at = datetime.datetime.now()
        ))
        db.session.commit()
        flash('Your changes have been saved')
        return redirect(p.url()), 303
    return render_template('edit.html', p=p)

