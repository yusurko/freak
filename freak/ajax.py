
'''
AJAX hooks for the OLD frontend.

DEPRECATED in 0.5 in favor of /v1/ (REST)
'''

from __future__ import annotations

import re
from quart import Blueprint, abort, flash, redirect, request
from sqlalchemy import delete, insert, select

from freak import UserLoader
from freak.utils import get_request_form
from .models import Guild, Member, UserBlock, db, User, Post, PostUpvote, username_is_legal
from quart_auth import current_user, login_required

current_user: UserLoader

bp = Blueprint('ajax', __name__)

@bp.route('/username_availability/<username>')
@bp.route('/ajax/username_availability/<username>')
async def username_availability(username: str):
    is_valid = username_is_legal(username)

    if is_valid:
        async with db as session:
            user = (await session.execute(select(User).where(User.username == username))).scalar()

            is_available = user is None or user == current_user.user
    else:
        is_available = False

    return {
        'status': 'ok',
        'is_valid': is_valid,
        'is_available': is_available
    }

@bp.route('/guild_name_availability/<name>')
async def guild_name_availability(name: str):
    is_valid = username_is_legal(name)

    if is_valid:
        async with db as session:
            gd = (await session.execute(select(Guild).where(Guild.name == name))).scalar()

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
async def post_upvote(id):
    form = await get_request_form()
    o = form['o']
    async with db as session:
        p: Post | None = (await session.execute(select(Post).where(Post.id == id))).scalar()

        if p is None:
            return { 'status': 'fail', 'message': 'Post not found' }, 404
        
        cur_score = await p.upvoted_by(current_user.user)

        match (o, cur_score):
            case ('1', 0) | ('1', -1):
                await session.execute(delete(PostUpvote).where(PostUpvote.c.post_id == p.id, PostUpvote.c.voter_id == current_user.id, PostUpvote.c.is_downvote == True))
                await session.execute(insert(PostUpvote).values(post_id = p.id, voter_id = current_user.id, is_downvote = False))
            case ('0', _):
                await session.execute(delete(PostUpvote).where(PostUpvote.c.post_id == p.id, PostUpvote.c.voter_id == current_user.id))
            case ('-1', 1) | ('-1', 0):
                await session.execute(delete(PostUpvote).where(PostUpvote.c.post_id == p.id, PostUpvote.c.voter_id == current_user.id, PostUpvote.c.is_downvote == False))
                await session.execute(insert(PostUpvote).values(post_id = p.id, voter_id = current_user.id, is_downvote = True))
            case ('1', 1) | ('-1', -1):
                pass
            case _:
                await session.rollback()
                return { 'status': 'fail', 'message': 'Invalid score' }, 400
        
        await session.commit()
        return { 'status': 'ok', 'count': await p.upvotes() }

@bp.route('/@<username>/block', methods=['POST'])
@login_required
async def block_user(username):
    form = await get_request_form()

    async with db as session:
        u = (await session.execute(select(User).where(User.username == username))).scalar()
        
        if u is None:
            abort(404)
        
        is_block = 'reverse' not in form
        is_unblock = form.get('reverse') == '1'

        if is_block:
            if current_user.has_blocked(u):
                await flash(f'{u.handle()} is already blocked')
            else:
                await session.execute(insert(UserBlock).values(
                    actor_id = current_user.id,
                    target_id = u.id
                ))
                await flash(f'{u.handle()} is now blocked')

        if is_unblock:
            if not current_user.has_blocked(u):
                await flash('You didn\'t block this user')
            else:
                await session.execute(delete(UserBlock).where(
                    UserBlock.c.actor_id == current_user.id,
                    UserBlock.c.target_id == u.id
                ))
                await flash(f'Removed block on {u.handle()}')
            
    return redirect(request.args.get('next', u.url())), 303

@bp.route('/+<name>/subscribe', methods=['POST'])
@login_required
async def subscribe_guild(name):
    form = await get_request_form()

    async with db as session:
        gu = (await session.execute(select(Guild).where(Guild.name == name))).scalar()

        if gu is None:
            abort(404)
        
        is_join = 'reverse' not in form
        is_leave = form.get('reverse') == '1'

        membership = (await session.execute(select(Member).where(Member.guild == gu, Member.user_id == current_user.id))).scalar()

        if is_join:
            if membership is None:
                membership = (await session.execute(insert(Member).values(
                    guild_id = gu.id,
                    user_id = current_user.id,
                    is_subscribed = True
                ).returning(Member))).scalar()
            elif membership.is_subscribed == False:
                membership.is_subscribed = True
                await session.add(membership)
            else:
                return redirect(gu.url()), 303
            await flash(f"You are now subscribed to {gu.handle()}")

        if is_leave:
            if membership is None:
                return redirect(gu.url()), 303
            elif membership.is_subscribed == True:
                membership.is_subscribed = False
                await session.add(membership)
            else:
                return redirect(gu.url()), 303

            await session.commit()
            await flash(f"Unsubscribed from {gu.handle()}.")
    
    return redirect(gu.url()), 303


