
from __future__ import annotations
from quart import Blueprint, abort, flash, render_template, request
from quart_auth import current_user, login_required
from sqlalchemy import select
import datetime

from .. import UserLoader
from ..utils import get_request_form

from ..models import db, User, Guild

current_user: UserLoader

bp = Blueprint('moderation', __name__)

@bp.route('/+<name>/settings', methods=['GET', 'POST'])
@login_required
async def guild_settings(name: str):
    form = await get_request_form()

    async with db as session:
        gu = (await session.execute(select(Guild).where(Guild.name == name))).scalar()

        if not current_user.moderates(gu):
            abort(403)

        if request.method == 'POST':
            if current_user.is_administrator and form.get('transfer_owner') == current_user.username:
                gu.owner_id = current_user.id
                await session.add(gu)
                await session.commit()
                await flash(f'Claimed ownership of {gu.handle()}')
                return await render_template('guildsettings.html', gu=gu)

        changes = False
        display_name: str = form.get('display_name')
        description: str = form.get('description')
        exile_name: str = form.get('exile_name')
        exile_reverse = 'exile_reverse' in form
        restricted = 'restricted' in form
        moderator_name: str = form.get('moderator_name')
        moderator_consent = 'moderator_consent' in form

        if description and description != gu.description:
            changes, gu.description = True, description.strip()
        if display_name and display_name != gu.display_name:
            changes, gu.display_name = True, display_name.strip()
        if exile_name:
            exile_user = (await session.execute(select(User).where(User.username == exile_name))).scalar()
            if exile_user:
                if exile_reverse:
                    mem = await gu.update_member(exile_user, banned_at = None, banned_by_id = None)
                    if mem.banned_at == None:
                        await flash(f'Removed ban on {exile_user.handle()}')
                        changes = True
                else:
                    mem = await gu.update_member(exile_user, banned_at = datetime.datetime.now(), banned_by_id = current_user.id)
                    if mem.banned_at != None:
                        await flash(f'{exile_user.handle()} has been exiled')
                        changes = True
            else:
                await flash(f'User \'{exile_name}\' not found, can\'t exile')
        if restricted and restricted != gu.is_restricted:
            changes, gu.is_restricted = True, restricted
        if moderator_consent and moderator_name:
            mu = (await session.execute(select(User).where(User.username == moderator_name))).scalar()
            if mu is None:
                await flash(f'User \'{moderator_name}\' not found')
            elif mu.is_disabled:
                await flash('Suspended users can\'t be moderators')
            elif mu.has_blocked(current_user.user):
                await flash(f'User \'{moderator_name}\' not found')
            else:
                mm = await gu.update_member(mu)
                if mm.is_moderator:
                    await flash(f'{mu.handle()} is already a moderator')
                elif mm.is_banned:
                    await flash('Exiled users can\'t be moderators')
                else:
                    mm.is_moderator = True
                    await session.add(mm)
                    changes = True


        if changes:
            session.add(gu)
            session.commit()
            await flash('Changes saved!')
    
    return render_template('guildsettings.html', gu=gu)

