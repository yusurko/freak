
'''
AJAX hooks for the website.

2025 DEPRECATED in favor of /v1/ (REST)
'''

import re
from flask import Blueprint, abort, flash, redirect, request
from sqlalchemy import delete, insert, select
from .models import Guild, Member, UserBlock, db, User, Post, PostUpvote, username_is_legal
from flask_login import current_user, login_required

current_user: User

bp = Blueprint('ajax', __name__)

@bp.route('/username_availability/<username>')
@bp.route('/ajax/username_availability/<username>')
def username_availability(username: str):
    is_valid = username_is_legal(username)

    if is_valid:
        user = db.session.execute(select(User).where(User.username == username)).scalar()

        is_available = user is None or user == current_user
    else:
        is_available = False

    return {
        'status': 'ok',
        'is_valid': is_valid,
        'is_available': is_available
    }

@bp.route('/guild_name_availability/<username>')
def guild_name_availability(name: str):
    is_valid = re.fullmatch('[a-z0-9_-]+', name) is not None

    if is_valid:
        gd = db.session.execute(select(Guild).where(Guild.name == name)).scalar()

        is_available = gd is None
    else:
        is_available = False

    return {
        'status': 'ok',
        'is_valid': is_valid,
        'is_available': is_available
    }

@bp.route('/comments/<b32l:id>/upvote', methods=['POST'])
@login_required
def post_upvote(id):
    o = request.form['o']
    p: Post | None = db.session.execute(select(Post).where(Post.id == id)).scalar()

    if p is None:
        return { 'status': 'fail', 'message': 'Post not found' }, 404
    
    if o == '1':
        db.session.execute(delete(PostUpvote).where(PostUpvote.c.post_id == p.id, PostUpvote.c.voter_id == current_user.id, PostUpvote.c.is_downvote == True))
        db.session.execute(insert(PostUpvote).values(post_id = p.id, voter_id = current_user.id, is_downvote = False))
    elif o == '0':
        db.session.execute(delete(PostUpvote).where(PostUpvote.c.post_id == p.id, PostUpvote.c.voter_id == current_user.id))
    elif o == '-1':
        db.session.execute(delete(PostUpvote).where(PostUpvote.c.post_id == p.id, PostUpvote.c.voter_id == current_user.id, PostUpvote.c.is_downvote == False))
        db.session.execute(insert(PostUpvote).values(post_id = p.id, voter_id = current_user.id, is_downvote = True))
    else:
        return { 'status': 'fail', 'message': 'Invalid score' }, 400

    db.session.commit()
    return { 'status': 'ok', 'count': p.upvotes() }

@bp.route('/@<username>/block', methods=['POST'])
@login_required
def block_user(username):
    u = db.session.execute(select(User).where(User.username == username)).scalar()
    
    if u is None:
        abort(404)
    
    is_block = 'reverse' not in request.form
    is_unblock = request.form.get('reverse') == '1'

    if is_block:
        if current_user.has_blocked(u):
            flash(f'{u.handle()} is already blocked')
        else:
            db.session.execute(insert(UserBlock).values(
                actor_id = current_user.id,
                target_id = u.id
            ))
            db.session.commit()
            flash(f'{u.handle()} is now blocked')

    if is_unblock:
        if not current_user.has_blocked(u):
            flash('You didn\'t block this user')
        else:
            db.session.execute(delete(UserBlock).where(
                UserBlock.c.actor_id == current_user.id,
                UserBlock.c.target_id == u.id
            ))
            db.session.commit()
            flash(f'Removed block on {u.handle()}')
        
    return redirect(request.args.get('next', u.url())), 303

@bp.route('/+<name>/subscribe', methods=['POST'])
@login_required
def subscribe_guild(name):
    gu = db.session.execute(select(Guild).where(Guild.name == name)).scalar()

    if gu is None:
        abort(404)
    
    is_join = 'reverse' not in request.form
    is_leave = request.form.get('reverse') == '1'

    membership = db.session.execute(select(Member).where(Member.guild == gu, Member.user_id == current_user.id)).scalar()

    if is_join:
        if membership is None:
            membership = db.session.execute(insert(Member).values(
                guild_id = gu.id,
                user_id = current_user.id,
                is_subscribed = True
            ).returning(Member)).scalar()
        elif membership.is_subscribed == False:
            membership.is_subscribed = True
            db.session.add(membership)
        else:
            return redirect(gu.url()), 303
        db.session.commit()
        flash(f"You are now subscribed to {gu.handle()}")

    if is_leave:
        if membership is None:
            return redirect(gu.url()), 303
        elif membership.is_subscribed == True:
            membership.is_subscribed = False
            db.session.add(membership)
        else:
            return redirect(gu.url()), 303

        db.session.commit()
        flash(f"Unsubscribed from {gu.handle()}.")
    
    return redirect(gu.url()), 303


