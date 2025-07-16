
from flask import Blueprint, abort, flash, render_template, request
from flask_login import current_user, login_required
from sqlalchemy import select
import datetime

from ..models import Member, db, User, Guild

current_user: User

bp = Blueprint('moderation', __name__)

@bp.route('/+<name>/settings', methods=['GET', 'POST'])
@login_required
def guild_settings(name: str):
    gu = db.session.execute(select(Guild).where(Guild.name == name)).scalar()

    if not current_user.moderates(gu):
        abort(403)

    if request.method == 'POST':
        if current_user.is_administrator and request.form.get('transfer_owner') == current_user.username:
            gu.owner_id = current_user.id
            db.session.add(gu)
            db.session.commit()
            flash(f'Claimed ownership of {gu.handle()}')
            return render_template('guildsettings.html', gu=gu)

        changes = False
        display_name = request.form.get('display_name')
        description = request.form.get('description')
        exile_name = request.form.get('exile_name')
        exile_reverse = 'exile_reverse' in request.form
        restricted = 'restricted' in request.form
        moderator_name = request.form.get('moderator_name')
        moderator_consent = 'moderator_consent' in request.form

        if description and description != gu.description:
            changes, gu.description = True, description.strip()
        if display_name and display_name != gu.display_name:
            changes, gu.display_name = True, display_name.strip()
        if exile_name:
            exile_user = db.session.execute(select(User).where(User.username == exile_name)).scalar()
            if exile_user:
                if exile_reverse:
                    mem = gu.update_member(exile_user, banned_at = None, banned_by_id = None)
                    if mem.banned_at == None:
                        flash(f'Removed ban on {exile_user.handle()}')
                        changes = True
                else:
                    mem = gu.update_member(exile_user, banned_at = datetime.datetime.now(), banned_by_id = current_user.id)
                    if mem.banned_at != None:
                        flash(f'{exile_user.handle()} has been exiled')
                        changes = True
            else:
                flash(f'User \'{exile_name}\' not found, can\'t exile')
        if restricted and restricted != gu.is_restricted:
            changes, gu.is_restricted = True, restricted
        if moderator_consent and moderator_name:
            mu = db.session.execute(select(User).where(User.username == moderator_name)).scalar()
            if mu is None:
                flash(f'User \'{moderator_name}\' not found')
            elif mu.is_disabled:
                flash('Suspended users can\'t be moderators')
            elif mu.has_blocked(current_user):
                flash(f'User \'{moderator_name}\' not found')
            else:
                mm = gu.update_member(mu)
                if mm.is_moderator:
                    flash(f'{mu.handle()} is already a moderator')
                elif mm.is_banned:
                    flash('Exiled users can\'t be moderators')
                else:
                    mm.is_moderator = True
                    db.session.add(mm)
                    changes = True


        if changes:
            db.session.add(gu)
            db.session.commit()
            flash('Changes saved!')
    
    return render_template('guildsettings.html', gu=gu)

