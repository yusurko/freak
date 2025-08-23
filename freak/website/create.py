

import sys
import datetime
from quart import Blueprint, abort, redirect, flash, render_template, request, url_for
from quart_auth import current_user, login_required
from sqlalchemy import insert, select

from freak import UserLoader
from freak.utils import get_request_form
from ..models import User, db, Guild, Post

current_user: UserLoader

bp = Blueprint('create', __name__)

async def create_savepoint(
    target = '', title = '',  content = '',
    privacy = 0
):
    return await render_template('create.html',
        sv_target = target,
        sv_title = title,
        sv_content = content,
        sv_privacy = privacy
    )

@bp.route('/create/', methods=['GET', 'POST'])
@login_required
async def create():
    user: User = current_user.user
    form = await get_request_form()
    if request.method == 'POST' and 'title' in form:
        gname = form['to']
        title = form['title']
        text = form['text']
        privacy = int(form.get('privacy', '0'))

        async with db as session:
            if gname:
                guild: Guild | None = (await session.execute(select(Guild).where(Guild.name == gname))).scalar()
                if guild is None:
                    await flash(f'Guild +{gname} not found or inaccessible')
                    return await create_savepoint('', title, text, privacy)
                if guild.has_exiled(user):
                    await flash(f'You are banned from +{gname}')
                    return await create_savepoint('', title, text, privacy)
                if not guild.allows_posting(user):
                    await flash(f'You can\'t post on +{gname}')
                    return await create_savepoint('', title, text, privacy)
            else:
                guild = None
            try:
                new_post_id: int = (await session.execute(insert(Post).values(
                    author_id = user.id,
                    topic_id = guild.id if guild else None,
                    created_at = datetime.datetime.now(),
                    privacy = privacy,
                    title = title,
                    text_content = text
                ).returning(Post.id))).scalar()
                
                session.commit()
                await flash(f'Published on {guild.handle() if guild else user.handle()}')
                return redirect(url_for('detail.post_detail', id=new_post_id))
            except Exception as e:
                sys.excepthook(*sys.exc_info())
                await flash('Unable to publish!')
    return await create_savepoint(target=request.args.get('on',''))


@bp.route('/createguild/', methods=['GET', 'POST'])
@login_required
async def createguild():
    if request.method == 'POST':
        if not current_user.user.can_create_community():
            await flash('You are NOT allowed to create new guilds.')
            abort(403)
        
        form = await get_request_form()

        c_name = form['name']
        try:
            async with db as session:
                new_guild = (await session.execute(insert(Guild).values(
                    name = c_name,
                    display_name = form.get('display_name', c_name),
                    description = form['description'],
                    owner_id = current_user.id
                ).returning(Guild))).scalar()

                if new_guild is None:
                    raise RuntimeError('no returning')

                await session.commit()
                return redirect(new_guild.url())
        except Exception:
            sys.excepthook(*sys.exc_info())
            await flash('Unable to create guild. It may already exist or you could not have permission to create new communities.')
    return await render_template('createguild.html')

@bp.route('/createcommunity/')
async def createcommunity_redirect():
    return redirect(url_for('create.createguild')), 301