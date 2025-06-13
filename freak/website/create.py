

import sys
import datetime
from flask import Blueprint, abort, redirect, flash, render_template, request, url_for
from flask_login import current_user, login_required
from sqlalchemy import insert
from ..models import User, db, Topic, Post

bp = Blueprint('create', __name__)

@bp.route('/create/', methods=['GET', 'POST'])
@login_required
def create():
    user: User = current_user
    if request.method == 'POST' and 'title' in request.form:
        topic_name = request.form['to']
        if topic_name:
            topic: Topic | None = db.session.execute(db.select(Topic).where(Topic.name == topic_name)).scalar()
            if topic is None:
                flash(f'Topic +{topic_name} not found, posting to your user page instead')
        else:
            topic = None
        title = request.form['title']
        text = request.form['text']
        privacy = int(request.form.get('privacy', '0'))
        try:
            new_post: Post = db.session.execute(insert(Post).values(
                author_id = user.id,
                topic_id = topic.id if topic else None,
                created_at = datetime.datetime.now(),
                privacy = privacy,
                title = title,
                text_content = text
            ).returning(Post.id)).fetchone()

            db.session.commit()
            flash(f'Published on {'+' + topic_name if topic_name else '@' + user.username}')
            return redirect(url_for('detail.post_detail', id=new_post.id))
        except Exception as e:
            sys.excepthook(*sys.exc_info())
            flash('Unable to publish!')
    return render_template('create.html')


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
            c_id = db.session.execute(db.insert(Topic).values(
                name = c_name,
                display_name = request.form.get('display_name', c_name),
                description = request.form['description'],
                owner_id = user.id
            ).returning(Topic.id)).fetchone()

            db.session.commit()
            return redirect(url_for('frontpage.topic_feed', name=c_name))
        except Exception:
            sys.excepthook(*sys.exc_info())
            flash('Unable to create guild. It may already exist or you could not have permission to create new communities.')
    return render_template('createguild.html')

@bp.route('/createcommunity/')
def createcommunity_redirect():
    return redirect(url_for('create.createguild')), 301