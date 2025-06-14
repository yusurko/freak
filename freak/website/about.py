
import sys
from flask import Blueprint, render_template, __version__ as flask_version
from sqlalchemy import __version__ as sa_version

bp = Blueprint('about', __name__)

@bp.route('/about/')
def about():
    return render_template('about.html',
        flask_version=flask_version,
        sa_version=sa_version,
        python_version=sys.version.split()[0]
    )

@bp.route('/terms/')
def terms():
    return render_template('terms.html')

@bp.route('/privacy/')
def privacy():
    return render_template('privacy.html')

@bp.route('/rules/')
def rules():
    return render_template('rules.html')

