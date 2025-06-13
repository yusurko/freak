
from flask import Blueprint, abort, flash, request, redirect, render_template, url_for
from flask_login import current_user, login_required
from sqlalchemy import select

from ..iding import id_from_b32l
from ..utils import is_b32l
from ..models import Comment, db, User, Post, Topic
from ..algorithms import user_timeline

bp = Blueprint('detail', __name__)

@bp.route('/@<username>')
def user_profile(username):
    user = db.session.execute(select(User).where(User.username == username)).scalar()

    if user is None:
        abort(404)

    posts = user_timeline(user.id)

    return render_template('userfeed.html', l=db.paginate(posts), user=user)


@bp.route('/u/<username>')
@bp.route('/user/<username>')
def user_profile_u(username: str):
    if is_b32l(username):
        userid = id_from_b32l(username)
        user = db.session.execute(select(User).where(User.id == userid)).scalar()
        if user is not None:
            username = user.username
    return redirect('/@' + username), 302


@bp.route('/@<username>/')
def user_profile_s(username):
    return redirect('/@' + username), 301


def single_post_post_hook(p: Post):
    if 'reply_to' in request.form:
        reply_to_id = request.form['reply_to']
        text = request.form['text']
        reply_to_p = db.session.execute(db.select(Post).where(Post.id == id_from_b32l(reply_to_id))).scalar() if reply_to_id else None

        db.session.execute(db.insert(Comment).values(
            author_id = current_user.id,
            parent_post_id = p.id,
            parent_comment_id = reply_to_p,
            text_content = text
        ))
        db.session.commit()
        flash('Comment published')
        return redirect(p.url()), 303
    abort(501)

@bp.route('/comments/<b32l:id>')
def post_detail(id: int):
    post: Post | None = db.session.execute(db.select(Post).where(Post.id == id)).scalar()

    if post and post.url() != request.full_path:
        return redirect(post.url()), 302
    else:
        abort(404)

@bp.route('/@<username>/comments/<b32l:id>/', methods=['GET', 'POST'])
@bp.route('/@<username>/comments/<b32l:id>/<slug:slug>', methods=['GET', 'POST'])
def user_post_detail(username: str, id: int, slug: str = ''):
    post: Post | None = db.session.execute(select(Post).join(User, User.id == Post.author_id).where(Post.id == id, User.username == username)).scalar()

    if post is None or (post.is_removed and post.author != current_user):
        abort(404)

    if post.slug and not slug:
        return redirect(url_for('detail.user_post_detail_slug', username=username, id=id, slug=post.slug)), 302

    if request.method == 'POST':
        single_post_post_hook(post)

    return render_template('singlepost.html', p=post)

@bp.route('/+<topicname>/comments/<b32l:id>/', methods=['GET', 'POST'])
@bp.route('/+<topicname>/comments/<b32l:id>/<slug:slug>', methods=['GET', 'POST'])
def topic_post_detail(topicname, id, slug=''):
    post: Post | None = db.session.execute(select(Post).join(Topic).where(Post.id == id, Topic.name == topicname)).scalar()

    if post is None or (post.is_removed and post.author != current_user):
        abort(404)

    if post.slug and not slug:
        return redirect(url_for('detail.topic_post_detail_slug', topicname=topicname, id=id, slug=post.slug)), 302

    if request.method == 'POST':
        single_post_post_hook(post)

    return render_template('singlepost.html', p=post)



