
'''
AJAX hooks for the website.

2025 DEPRECATED in favor of /v1/ (REST)
'''

import re
from flask import Blueprint, request
from .models import Topic, db, User, Post, PostUpvote
from flask_login import current_user, login_required

bp = Blueprint('ajax', __name__)

@bp.route('/username_availability/<username>')
@bp.route('/ajax/username_availability/<username>')
def username_availability(username: str):
    is_valid = re.fullmatch('[a-z0-9_-]+', username) is not None

    if is_valid:
        user = db.session.execute(db.select(User).where(User.username == username)).scalar()

        is_available = user is None or user == current_user
    else:
        is_available = False

    return {
        'status': 'ok',
        'is_valid': is_valid,
        'is_available': is_available,
    }

@bp.route('/guild_name_availability/<username>')
def guild_name_availability(name: str):
    is_valid = re.fullmatch('[a-z0-9_-]+', username) is not None

    if is_valid:
        gd = db.session.execute(db.select(Topic).where(Topic.name == name)).scalar()

        is_available = gd is None
    else:
        is_available = False

    return {
        'status': 'ok',
        'is_valid': is_valid,
        'is_available': is_available,
    }

@bp.route('/comments/<b32l:id>/upvote', methods=['POST'])
@login_required
def post_upvote(id):
    o = request.form['o']
    p: Post | None = db.session.execute(db.select(Post).where(Post.id == id)).scalar()

    if p is None:
        return { 'status': 'fail', 'message': 'Post not found' }, 404
    
    if o == '1':
        db.session.execute(db.delete(PostUpvote).where(PostUpvote.c.post_id == p.id, PostUpvote.c.voter_id == current_user.id, PostUpvote.c.is_downvote == True))
        db.session.execute(db.insert(PostUpvote).values(post_id = p.id, voter_id = current_user.id, is_downvote = False))
    elif o == '0':
        db.session.execute(db.delete(PostUpvote).where(PostUpvote.c.post_id == p.id, PostUpvote.c.voter_id == current_user.id))
    elif o == '-1':
        db.session.execute(db.delete(PostUpvote).where(PostUpvote.c.post_id == p.id, PostUpvote.c.voter_id == current_user.id, PostUpvote.c.is_downvote == False))
        db.session.execute(db.insert(PostUpvote).values(post_id = p.id, voter_id = current_user.id, is_downvote = True))
    else:
        return { 'status': 'fail', 'message': 'Invalid score' }, 400

    db.session.commit()
    return { 'status': 'ok', 'count': p.upvotes() }

