

from __future__ import annotations

from quart import Blueprint, render_template, redirect, abort, request
from quart_auth import current_user
from sqlalchemy import and_, distinct, func, select

from freak import UserLoader
from freak.utils import get_request_form

from ..search import SearchQuery
from ..models import Guild, Member, Post, User, db
from ..algorithms import public_timeline, top_guilds_query, topic_timeline

current_user: UserLoader

bp = Blueprint('frontpage', __name__)



@bp.route('/')
async def homepage():
    async with db as session:
        top_communities = [(x[0], x[1], x[2]) for x in 
                (await session.execute(top_guilds_query().limit(10))).fetchall()]

    if current_user:
        # renders user's own timeline
        # TODO this is currently the public timeline.

        return await render_template('feed.html', feed_type='foryou', l=await db.paginate(public_timeline()),
            top_communities=top_communities)
    else:
        # Show a landing page to anonymous users.
        return await render_template('landing.html', top_communities=top_communities)


@bp.route('/explore/')
async def explore():
    return render_template('feed.html', feed_type='explore', l=db.paginate(public_timeline()))


@bp.route('/+<name>/')
async def guild_feed(name):
    async with db as session:
        guild: Guild | None = (await session.execute(select(Guild).where(Guild.name == name))).scalar()

        if guild is None:
            abort(404)

        posts = await db.paginate(topic_timeline(name))

        return await render_template(
            'feed.html', feed_type='guild', feed_title=f'{guild.display_name} (+{guild.name})', l=posts, guild=guild,
            current_guild=guild)

@bp.route('/r/<name>/')
async def guild_feed_r(name):
    return redirect('/+' + name + '/'), 302


@bp.route("/search", methods=["GET", "POST"])
async def search():
    if request.method == "POST":
        form = await get_request_form()
        q = form["q"]
        if q:
            results = db.paginate(SearchQuery(q).select(Post, [Post.title]).order_by(Post.created_at.desc()))
        else:
            results = None
        return await render_template(
                "search.html",
                results=results,
                q = q
            )
    return await render_template("search.html")
