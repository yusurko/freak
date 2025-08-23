
import sys
from quart import Blueprint, render_template
import importlib.metadata
try:
    from quart import __version__ as quart_version
except Exception:
    quart_version = importlib.metadata.version('quart')
from sqlalchemy import __version__ as sa_version

bp = Blueprint('about', __name__)

@bp.route('/about/')
async def about():
    return await render_template('about.html',
        quart_version=quart_version,
        sa_version=sa_version,
        python_version=sys.version.split()[0]
    )

@bp.route('/terms/')
async def terms():
    return await render_template('terms.html')

@bp.route('/privacy/')
async def privacy():
    return await render_template('privacy.html')

@bp.route('/rules/')
async def rules():
    return await render_template('rules.html')

