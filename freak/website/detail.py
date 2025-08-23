
from __future__ import annotations

from typing import Iterable
from quart import Blueprint, abort, flash, request, redirect, render_template, url_for
from quart_auth import current_user
from sqlalchemy import insert, select
from suou import Snowflake

from freak import UserLoader

from ..utils import get_request_form, is_b32l
from ..models import Comment, Guild, db, User, Post
from ..algorithms import new_comments, user_timeline

current_user: UserLoader

bp = Blueprint('detail', __name__)

@bp.route('/@<username>')
async def user_profile(username):
    async with db as session:
        user = (await session.execute(select(User).where(User.username == username))).scalar()

        if user is None:
            abort(404)

        posts = await db.paginate(user_timeline(user))
        print(posts.pages)

        return await render_template('userfeed.html', l=posts, user=user)


@bp.route('/u/<username>')
@bp.route('/user/<username>')
async def user_profile_u(username: str):
    if is_b32l(username):
        userid = int(Snowflake.from_b32l(username))
        async with db as session:
            user = (await session.execute(select(User).where(User.id == userid))).scalar()
            if user is not None:
                username = user.username
                return redirect('/@' + username), 302
    return redirect('/@' + username), 301


@bp.route('/@<username>/')
async def user_profile_s(username):
    return redirect('/@' + username), 301


async def single_post_post_hook(p: Post):
    if p.guild is not None:
        gu = p.guild
        if gu.has_exiled(current_user.user):
            await flash(f'You have been banned from {gu.handle()}')
            return

        if not gu.allows_posting(current_user.user):
            await flash(f'You can\'t post in {gu.handle()}')
            return

    if p.is_locked:
        await flash(f'You can\'t comment on locked posts')
        return

    form = await get_request_form()
    if 'reply_to' in form:
        reply_to_id = form['reply_to']
        text = form['text']

        async with db as session:
            reply_to_p = (await session.execute(select(Post).where(Post.id == int(Snowflake.from_b32l(reply_to_id))))).scalar() if reply_to_id else None

            session.execute(insert(Comment).values(
                author_id = current_user.id,
                parent_post_id = p.id,
                parent_comment_id = reply_to_p,
                text_content = text
            ))
            session.commit()
            await flash('Comment published')
            return redirect(p.url()), 303
    abort(501)

@bp.route('/comments/<b32l:id>')
async def post_detail(id: int):
    async with db as session:
        post: Post | None = (await session.execute(select(Post).where(Post.id == id))).scalar()

    if post and post.url() != request.full_path:
        return redirect(post.url()), 302
    else:
        abort(404)

async def comments_of(p: Post) -> Iterable[Comment]:
    ## TODO add sort argument
    pp = await db.paginate(new_comments(p))
    print(pp.pages)
    return pp


@bp.route('/@<username>/comments/<b32l:id>/', methods=['GET', 'POST'])
@bp.route('/@<username>/comments/<b32l:id>/<slug:slug>', methods=['GET', 'POST'])
async def user_post_detail(username: str, id: int, slug: str = ''):
    async with db as session:
        post: Post | None = (await session.execute(select(Post).join(User, User.id == Post.author_id).where(Post.id == id, User.username == username))).scalar()

        if post is None or (post.author and await post.author.has_blocked(current_user.user)) or (post.is_removed and post.author != current_user.user):
            abort(404)

        if post.slug and slug != post.slug:
            return redirect(post.url()), 302

        if request.method == 'POST':
            single_post_post_hook(post)

        return await render_template('singlepost.html', p=post, comments=await comments_of(post))

@bp.route('/+<gname>/comments/<b32l:id>/', methods=['GET', 'POST'])
@bp.route('/+<gname>/comments/<b32l:id>/<slug:slug>', methods=['GET', 'POST'])
async def guild_post_detail(gname, id, slug=''):
    async with db as session:
        post: Post | None = (await session.execute(select(Post).join(Guild).where(Post.id == id, Guild.name == gname))).scalar()

        if post is None or (post.author and await post.author.has_blocked(current_user.user)) or (post.is_removed and post.author != current_user.user):
            abort(404)

        if post.slug and slug != post.slug:
            return redirect(post.url()), 302

        if request.method == 'POST':
            single_post_post_hook(post)

        return await render_template('singlepost.html', p=post, comments=await comments_of(post), current_guild = post.guild)



