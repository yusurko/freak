
from flask import Blueprint, abort, flash, render_template, request
from flask_login import current_user, login_required
from sqlalchemy import select

from ..models import db, User, Guild

current_user: User

bp = Blueprint('moderation', __name__)

@bp.route('/+<name>/settings', methods=['GET', 'POST'])
@login_required
def guild_settings(name: str):
    gu = db.session.execute(select(Guild).where(Guild.name == name)).scalar()

    if not current_user.moderates(gu):
        abort(403)

    if request.method == 'POST':
        changes = False
        display_name = request.form.get('display_name')
        description = request.form.get('description')

        if description and description != gu.description:
            changes, gu.description = True, description.strip()
        if display_name and display_name != gu.display_name:
            changes, gu.display_name = True, display_name.strip()

        if changes:
            db.session.add(gu)
            db.session.commit()
        flash('Changes saved!')
    
    return render_template('guildsettings.html', gu=gu)

