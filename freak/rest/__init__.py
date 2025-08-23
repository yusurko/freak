
from __future__ import annotations

from flask import abort
from quart import Blueprint, redirect, url_for
from quart_auth import current_user, login_required
from quart_schema import QuartSchema, validate_request, validate_response
from sqlalchemy import select
from suou import Snowflake, deprecated, not_implemented, want_isodate

from suou.quart import add_rest

from ..models import Post, User, db
from .. import UserLoader, app, app_config,  __version__ as freak_version

bp = Blueprint('rest', __name__, url_prefix='/v1')
rest = add_rest(app, '/v1', '/ajax')

current_user: UserLoader

## TODO deprecate auth_required since it does not work
from suou.flask_sqlalchemy import require_auth
auth_required = deprecated('use login_required() and current_user instead')(require_auth(User, db))

@not_implemented()
async def authenticated():
    pass

@bp.get('/nurupo')
async def get_nurupo():
    return dict(ga=-1)

@bp.get('/health')
async def health():
    return dict(
        version=freak_version,
        name = app_config.app_name
    )

## TODO coverage of REST is still partial, but it's planned
## to get complete sooner or later

## XXX there is a bug in suou.sqlalchemy.auth_required() — apparently, /user/@me does not
## redirect, neither is able to get user injected.
## Auth-based REST endpoints won't be fully functional until 0.6 in most cases


@bp.get('/user/@me')
@login_required
async def get_user_me():
    return redirect(url_for(f'rest.user_get', current_user.id)), 302

@bp.get('/user/<b32l:id>')
async def user_get(id: int):
    ## TODO sanizize REST to make blocked users inaccessible
    async with db as session:
        u: User | None = (await session.execute(select(User).where(User.id == id))).scalar()
        if u is None:
            return dict(error='User not found'), 404
        uj = dict(
            id = f'{Snowflake(u.id):l}',
            username = u.username,
            display_name = u.display_name,
            joined_at = want_isodate(u.joined_at),
            karma = u.karma,
            age = u.age(),
            biography=u.biography,
            badges = u.badges()
        )
    return dict(users={f'{Snowflake(id):l}': uj})

@bp.get('/user/@<username>')
async def resolve_user(username: str):
    async with db as session:
        uid: User | None = (await session.execute(select(User.id).select_from(User).where(User.username == username))).scalar()
    if uid is None:
        abort(404, 'User not found')
    return redirect(url_for('rest.user_get', id=uid)), 302


@bp.get('/post/<b32l:id>')
async def get_post(id: int):
    async with db as session:
        p: Post | None = (await session.execute(select(Post).where(Post.id == id))).scalar()
        if p is None:
            return dict(error='Not found'), 404
        pj = dict(
            id = f'{Snowflake(p.id):l}',
            title = p.title,
            author = p.author.simple_info(),
            to = p.topic_or_user().handle(),
            created_at = p.created_at.isoformat('T')
        )

    return dict(posts={f'{Snowflake(id):l}': pj})
