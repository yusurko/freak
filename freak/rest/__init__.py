
from __future__ import annotations

from flask import abort
from pydantic import BaseModel
from quart import Blueprint, redirect, request, url_for
from quart_auth import AuthUser, current_user, login_required, login_user, logout_user
from quart_schema import QuartSchema, validate_request, validate_response
from sqlalchemy import select
from suou import Snowflake, deprecated, makelist, not_implemented, want_isodate

from werkzeug.security import check_password_hash
from suou.quart import add_rest

from freak.accounts import LoginStatus, check_login
from freak.algorithms import public_timeline, top_guilds_query, topic_timeline, user_timeline

from ..models import Guild, Post, User, db
from .. import UserLoader, app, app_config,  __version__ as freak_version, csrf

bp = Blueprint('rest', __name__, url_prefix='/v1')
rest = add_rest(app, '/v1', '/ajax')

## XXX potential security hole, but needed for REST to work
csrf.exempt(bp)

current_user: UserLoader

## TODO deprecate auth_required since it does not work
## will be removed in 0.6
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
    async with db as session:
        hi =  dict(
            version=freak_version,
            name = app_config.app_name,
            post_count = await Post.count(),
            user_count = await User.active_count(),
            me = Snowflake(current_user.id).to_b32l() if current_user else None
        )

        return hi

@bp.get('/oath')
async def oath():
    return dict(
        ## XXX might break any time!
        csrf_token= await csrf._get_csrf_token()
    )

## TODO coverage of REST is still partial, but it's planned
## to get complete sooner or later

## XXX there is a bug in suou.sqlalchemy.auth_required() — apparently, /user/@me does not
## redirect, neither is able to get user injected. It was therefore dismissed.
## Auth-based REST endpoints won't be fully functional until 0.6 in most cases

## USERS ##

@bp.get('/user/@me')
@login_required
async def get_user_me():
    return redirect(url_for(f'rest.user_get', id=current_user.id)), 302

def _user_info(u: User):
    return dict(
            id = f'{Snowflake(u.id):l}',
            username = u.username,
            display_name = u.display_name,
            joined_at = want_isodate(u.joined_at),
            karma = u.karma,
            age = u.age(),
            biography=u.biography,
            badges = u.badges()
        )

@bp.get('/user/<b32l:id>')
async def user_get(id: int):
    ## TODO sanizize REST to make blocked users inaccessible
    async with db as session:
        u: User | None = (await session.execute(select(User).where(User.id == id))).scalar()
        if u is None:
            return dict(error='User not found'), 404
        uj = _user_info(u)
    return dict(users={f'{Snowflake(id):l}': uj})

@bp.get('/user/<b32l:id>/feed')
async def user_feed_get(id: int):
    async with db as session:
        u: User | None = (await session.execute(select(User).where(User.id == id))).scalar()
        if u is None:
            return dict(error='User not found'), 404
        uj = _user_info(u)

        feed = []
        algo = user_timeline(u)
        posts = await db.paginate(algo)
        async for p in posts:
            feed.append(p.feed_info())

    return dict(users={f'{Snowflake(id):l}': uj}, feed=feed)

@bp.get('/user/@<username>')
async def resolve_user(username: str):
    async with db as session:
        uid: User | None = (await session.execute(select(User.id).select_from(User).where(User.username == username))).scalar()
    if uid is None:
        abort(404, 'User not found')
    return redirect(url_for('rest.user_get', id=uid)), 302

@bp.get('/user/@<username>/feed')
async def resolve_user_feed(username: str):
    async with db as session:
        uid: User | None = (await session.execute(select(User.id).select_from(User).where(User.username == username))).scalar()
    if uid is None:
        abort(404, 'User not found')
    return redirect(url_for('rest.user_feed_get', id=uid)), 302

## POSTS ##

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
            to = p.topic_or_user().simple_info(typed=True),
            created_at = p.created_at.isoformat('T')
        )

        if p.is_text_post():
            pj['content'] = p.text_content

    return dict(posts={f'{Snowflake(id):l}': pj})

## GUILDS ##

async def _guild_info(gu: Guild):
    return dict(
        id = f'{Snowflake(gu.id):l}',
        name = gu.name,
        display_name = gu.display_name,
        description = gu.description,
        created_at = want_isodate(gu.created_at),
        badges = []
    )

@bp.get('/guild/@<gname>')
async def guild_info_only(gname: str):
    async with db as session:
        gu: Guild | None = (await session.execute(select(Guild).where(Guild.name == gname))).scalar()

        if gu is None:
            return dict(error='Not found'), 404
        gj = await _guild_info(gu)
    
    return dict(guilds={f'{Snowflake(gu.id):l}': gj})


@bp.get('/guild/@<gname>/feed')
async def guild_feed(gname: str):
    async with db as session:
        gu: Guild | None = (await session.execute(select(Guild).where(Guild.name == gname))).scalar()

        if gu is None:
            return dict(error='Not found'), 404
        gj = await _guild_info(gu)
        feed = []
        algo = topic_timeline(gname)
        posts = await db.paginate(algo)
        async for p in posts:
            feed.append(p.feed_info())

    return dict(guilds={f'{Snowflake(gu.id):l}': gj}, feed=feed)

## LOGIN/OUT ##

class LoginIn(BaseModel):
    username: str
    password: str
    remember: bool = False

@bp.post('/login')
@validate_request(LoginIn)
async def login(data: LoginIn):
    async with db as session:
        u = (await session.execute(select(User).where(User.username == data.username))).scalar()
        match check_login(u, data.password):
            case LoginStatus.SUCCESS:
                remember_for = int(data.remember)
                if remember_for > 0:
                    login_user(UserLoader(u.get_id()), remember=True)
                else:
                    login_user(UserLoader(u.get_id()))
                return {'id': f'{Snowflake(u.id):l}'}, 200
            case LoginStatus.ERROR:
                abort(404, 'Invalid username or password')
            case LoginStatus.SUSPENDED:
                abort(403, 'Your account is suspended')
            case LoginStatus.PASS_EXPIRED:
                abort(403, 'You need to reset your password following the procedure.') 


@bp.post('/logout')
@login_required
async def logout():
    logout_user()
    return '', 204


## HOME ##

@bp.get('/home/feed')
@login_required
async def home_feed():
    async with db as session:
        me = current_user.user
        posts = await db.paginate(public_timeline())
        feed = []
        async for post in posts:
            feed.append(post.feed_info())

        return dict(feed=feed)


@bp.get('/top/guilds')
async def top_guilds():
    async with db as session:
        top_g = [await x.sub_info() for x in 
            (await session.execute(top_guilds_query().limit(10))).scalars()]

        return dict(has=top_g)
        
    

