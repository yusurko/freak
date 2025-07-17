

import sys
import datetime
from flask import Blueprint, abort, redirect, flash, render_template, request, url_for
from flask_login import current_user, login_required
from sqlalchemy import insert, select
from ..models import User, db, Guild, Post

current_user: User

bp = Blueprint('create', __name__)

def create_savepoint(
    target = '', title = '',  content = '',
    privacy = 0
):
    return render_template('create.html',
        sv_target = target,
        sv_title = title,
        sv_content = content,
        sv_privacy = privacy
    )

@bp.route('/create/', methods=['GET', 'POST'])
@login_required
def create():
    user: User = current_user
    if request.method == 'POST' and 'title' in request.form:
        gname = request.form['to']
        title = request.form['title']
        text = request.form['text']
        privacy = int(request.form.get('privacy', '0'))
        if gname:
            guild: Guild | None = db.session.execute(select(Guild).where(Guild.name == gname)).scalar()
            if guild is None:
                flash(f'Guild +{gname} not found or inaccessible')
                return create_savepoint('', title, text, privacy)
            if guild.has_exiled(user):
                flash(f'You are banned from +{gname}')
                return create_savepoint('', title, text, privacy)
            if not guild.allows_posting(user):
                flash(f'You can\'t post on +{gname}')
                return create_savepoint('', title, text, privacy)
        else:
            guild = None
        try:
            new_post: Post = db.session.execute(insert(Post).values(
                author_id = user.id,
                topic_id = guild.id if guild else None,
                created_at = datetime.datetime.now(),
                privacy = privacy,
                title = title,
                text_content = text
            ).returning(Post.id)).fetchone()

            db.session.commit()
            flash(f'Published on {guild.handle() if guild else user.handle()}')
            return redirect(url_for('detail.post_detail', id=new_post.id))
        except Exception as e:
            sys.excepthook(*sys.exc_info())
            flash('Unable to publish!')
    return create_savepoint(target=request.args.get('on',''))


@bp.route('/createguild/', methods=['GET', 'POST'])
@login_required
def createguild():
    if request.method == 'POST':
        user: User = current_user

        if not user.can_create_community():
            flash('You are NOT allowed to create new guilds.')
            abort(403)

        c_name = request.form['name']
        try:
            new_guild = db.session.execute(insert(Guild).values(
                name = c_name,
                display_name = request.form.get('display_name', c_name),
                description = request.form['description'],
                owner_id = user.id
            ).returning(Guild)).scalar()

            if new_guild is None:
                raise RuntimeError('no returning')

            db.session.commit()
            return redirect(new_guild.url())
        except Exception:
            sys.excepthook(*sys.exc_info())
            flash('Unable to create guild. It may already exist or you could not have permission to create new communities.')
    return render_template('createguild.html')

@bp.route('/createcommunity/')
def createcommunity_redirect():
    return redirect(url_for('create.createguild')), 301