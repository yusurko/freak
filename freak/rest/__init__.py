
from __future__ import annotations
import datetime
import sys
from typing import Iterable, TypeVar
import logging

from quart import render_template, session
from quart import abort, Blueprint, redirect, request, url_for
from pydantic import BaseModel, Field
from quart_auth import current_user, login_required, login_user, logout_user
from quart_schema import validate_request
from quart_wtf.csrf import generate_csrf
from sqlalchemy import delete, insert, select
from suou import Snowflake, deprecated, makelist, not_implemented, want_isodate

from suou.classtools import MISSING, MissingType
from werkzeug.security import check_password_hash
from suou.quart import add_rest

from freak.accounts import LoginStatus, check_login
from freak.algorithms import public_timeline, top_guilds_query, topic_timeline, user_timeline
from freak.search import SearchQuery

from ..models import Comment, Guild, Post, PostUpvote, User, db
from .. import UserLoader, app, app_config,  __version__ as freak_version, csrf

logger = logging.getLogger(__name__)
_T = TypeVar('_T')

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
        hi = dict(
            version=freak_version,
            name = app_config.app_name,
            post_count = await Post.count(),
            user_count = await User.active_count(),
            me = Snowflake(current_user.id).to_b32l() if current_user else None,
            color_theme = current_user.color_theme if current_user else 0
        )

        return hi

@bp.get('/oath')
async def oath():
    try:
        ## pull csrf token from session
        csrf_tok = session['csrf_token']
    except Exception as e:
        try:
            logger.warning('CSRF token regenerated!')
            csrf_tok = session['csrf_token'] = generate_csrf()
        except Exception as e2:
            print(e, e2)
            abort(503, "csrf_token is null")

    return dict(
        ## XXX might break any time!
        csrf_token= csrf_tok
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
            feed.append(await p.feed_info_counts())

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

        pj['comment_count'] = await p.comment_count()
        pj['votes'] = await p.upvotes()
        pj['my_vote'] = await p.upvoted_by(current_user.user)

    return dict(posts={f'{Snowflake(id):l}': pj})

class VoteIn(BaseModel):
    vote: int

@bp.post('/post/<b32l:id>/upvote')
@validate_request(VoteIn)
async def upvote_post(id: int, data: VoteIn):
    async with db as session:
        p: Post | None = (await session.execute(select(Post).where(Post.id == id))).scalar()

        if p is None:
            return { 'status': 404, 'error': 'Post not found' }, 404
        
        cur_score = await p.upvoted_by(current_user.user)

        match (data.vote, cur_score):
            case (1, 0) | (1, -1):
                await session.execute(delete(PostUpvote).where(PostUpvote.c.post_id == p.id, PostUpvote.c.voter_id == current_user.id, PostUpvote.c.is_downvote == True))
                await session.execute(insert(PostUpvote).values(post_id = p.id, voter_id = current_user.id, is_downvote = False))
            case (0, _):
                await session.execute(delete(PostUpvote).where(PostUpvote.c.post_id == p.id, PostUpvote.c.voter_id == current_user.id))
            case (-1, 1) | (-1, 0):
                await session.execute(delete(PostUpvote).where(PostUpvote.c.post_id == p.id, PostUpvote.c.voter_id == current_user.id, PostUpvote.c.is_downvote == False))
                await session.execute(insert(PostUpvote).values(post_id = p.id, voter_id = current_user.id, is_downvote = True))
            case (1, 1) | (1, -1):
                pass
            case _:
                await session.rollback()
                return { 'status': 400, 'error': 'Invalid score' }, 400
        
        await session.commit()
        return { 'votes': await p.upvotes() }

## COMMENTS ##

@bp.get('/post/<b32l:id>/comments')
async def post_comments (id: int):
    async with db as session:
        p: Post | None = (await session.execute(select(Post).where(Post.id == id))).scalar()

        if p is None:
            return { 'status': 404, 'error': 'Post not found' }, 404
        
        l = []
        for com in await p.top_level_comments():
            com: Comment
            l.append(await com.section_info())
        
        return dict(has=l)



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

@bp.get('/guild/<b32l:gid>')
async def guild_info_id(gid: int):
    async with db as session:
        gu: Guild | None = (await session.execute(select(Guild).where(Guild.id == gid))).scalar()

        if gu is None:
            return dict(error='Not found'), 404
        gj = await _guild_info(gu)
    
    return dict(guilds={f'{Snowflake(gu.id):l}': gj})

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
            feed.append(await p.feed_info_counts())

    return dict(guilds={f'{Snowflake(gu.id):l}': gj}, feed=feed)


## CREATE ##

class CreateIn(BaseModel):
    title: str
    content: str
    privacy: int = Field(default=0, ge=0, lt=4)

@bp.post('/guild/@<gname>')
@login_required
@validate_request(CreateIn)
async def guild_post(data: CreateIn, gname: str):
    async with db as session:
        user = current_user.user
        gu: Guild | None = (await session.execute(select(Guild).where(Guild.name == gname))).scalar()

        if gu is None:
            return dict(error='Not found'), 404
        if await gu.has_exiled(current_user.user):
            return dict(error=f'You are banned from +{gname}'), 403
        if not await gu.allows_posting(current_user.user):
            return dict(error=f'You can\'t post on +{gname}'), 403

        try: 
            new_post_id: int = (await session.execute(insert(Post).values(
                author_id = user.id,
                topic_id = gu.id,
                privacy = data.privacy,
                title = data.title,
                text_content = data.text
            ).returning(Post.id))).scalar()

            session.commit()
            return dict(id=Snowflake(new_post_id).to_b32l()), 200
        except Exception:
            sys.excepthook(*sys.exc_info())
            return {'error': 'Internal Server Error'}, 500

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
            feed.append(await post.feed_info_counts())

        return dict(feed=feed)


@bp.get('/top/guilds')
async def top_guilds():
    async with db as session:
        top_g = [await x.sub_info() for x in 
            (await session.execute(top_guilds_query().limit(10))).scalars()]

        return dict(has=top_g)

## SEARCH ##

class QueryIn(BaseModel):
    query: str

@bp.post('/search/top')
@validate_request(QueryIn)
async def search_top(data: QueryIn):
    async with db as session:
        sq = SearchQuery(data.query)

        result = (await session.execute(sq.select(Post, [Post.title]).limit(20))).scalars()
        
        return dict(has = [p.feed_info() for p in result])
    

## SUGGEST


@bp.post("/suggest/guild")
@validate_request(QueryIn)
async def suggest_guild(data: QueryIn):
    if not data.query.isidentifier():
        return dict(has=[])
    async with db as session:
        sq = select(Guild).where(Guild.name.like(data.query + "%"))

        result: Iterable[Guild] = (await session.execute(sq.limit(10))).scalars()

        return dict(has = [g.simple_info() for g in result if await g.allows_posting(current_user.user)])


## SETTINGS

@bp.get("/settings/appearance")
@login_required
async def get_settings_appearance():
    return dict(
        color_theme = current_user.user.color_theme
    )


class SettingsAppearanceIn(BaseModel):
    color_theme : int | None = None
    color_scheme : int | None = None


def _missing_or(obj: _T | MissingType, obj2: _T) -> _T:
    if obj is None:
        return obj2
    return obj

@bp.patch("/settings/appearance")
@login_required
@validate_request(SettingsAppearanceIn)
async def patch_settings_appearance(data: SettingsIn):
    u = current_user.user
    if u is None:
        abort(401)
    
    u.color_theme = (
        _missing_or(data.color_theme, u.color_theme % (1 << 8)) % 256 +
        _missing_or(data.color_scheme, u.color_theme >> 8) << 8
    )
    current_user.session.add(u)
    await current_user.session.commit()

    return '', 204

## TERMS

@bp.get('/about/about')
async def about_about():
    return dict(
        content=await render_template("about.md")
    )

@bp.get('/about/terms')
async def terms():
    return dict(
        content=await render_template("terms.md")
    )

@bp.get('/about/privacy')
async def privacy():
    return dict(
        content=await render_template("privacy.md")
    )

@bp.get('/about/rules')
async def rules():
    return dict(
        content=await render_template("rules.md")
    )
