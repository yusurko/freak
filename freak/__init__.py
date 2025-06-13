

from sqlite3 import ProgrammingError
import warnings
from flask import (
    Flask, abort, flash, g, jsonify, redirect, render_template,
    request, send_from_directory, url_for
)
import datetime, time, re, os, sys, string, json, html, dotenv
from flask_login import LoginManager
from flask_wtf.csrf import CSRFProtect
from sqlalchemy import select
from werkzeug.routing import BaseConverter
from sassutils.wsgi import SassMiddleware

__version__ = '0.3.0'

APP_BASE_DIR = os.path.dirname(os.path.dirname(__file__))

dotenv.load_dotenv(os.path.join(APP_BASE_DIR, '.env'))

correct_database_url = os.environ["DATABASE_URL"]

def fix_database_url():
    if os.getenv('DATABASE_URL') != correct_database_url:
        warnings.warn('mod_wsgi got the database wrong!', RuntimeWarning)
        app.config['SQLALCHEMY_DATABASE_URI'] = correct_database_url


app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY')
app.config['SQLALCHEMY_DATABASE_URI'] = correct_database_url
app.config['JSONIFY_PRETTYPRINT_REGULAR'] = False

from .models import db, User, Post
from .iding import id_from_b32l, id_to_b32l

# SASS
app.wsgi_app = SassMiddleware(app.wsgi_app, dict(
    freak=('static/sass', 'static/css', '/static/css', True)
))

class SlugConverter(BaseConverter):
    regex = r'[a-z0-9]+(?:-[a-z0-9]+)*'

class B32lConverter(BaseConverter):
    regex = r'_?[a-z2-7]+'
    def to_url(self, value):
        return id_to_b32l(value)
    def to_python(self, value):
        return id_from_b32l(value)

app.url_map.converters['slug'] = SlugConverter
app.url_map.converters['b32l'] = B32lConverter

db.init_app(app)

csrf = CSRFProtect(app)

login_manager = LoginManager(app)
login_manager.login_view = 'accounts.login'

from . import filters


PRIVATE_ASSETS = os.getenv('PRIVATE_ASSETS', '').split()

@app.context_processor
def _inject_variables():
    return {
        'app_name': os.getenv('APP_NAME'),
        'domain_name': os.getenv('DOMAIN_NAME'),
        'url_for_css': (lambda name, **kwargs: url_for('static', filename=f'css/{name}.css', **kwargs)),
        'private_scripts': [x for x in PRIVATE_ASSETS if x.endswith('.js')],
        'private_styles': [x for x in PRIVATE_ASSETS if x.endswith('.css')],
        'jquery_url': os.getenv('JQUERY_URL') or 'https://ajax.googleapis.com/ajax/libs/jquery/3.7.1/jquery.min.js',
        'post_count': Post.count(),
        'user_count': User.active_count()
    }

@login_manager.user_loader
def _inject_user(userid):
    try:
        return db.session.execute(select(User).where(User.id == userid)).scalar()
    except Exception:
        warnings.warn(f'cannot retrieve user {userid} from db', RuntimeWarning)
        g.no_user = True
        return None

@app.errorhandler(ProgrammingError)
def error_db(body):
    g.no_user = True
    warnings.warn(f'No database access! (url is {app.config['SQLALCHEMY_DATABASE_URI']})', RuntimeWarning)
    fix_database_url()
    if request.method in ('HEAD', 'GET') and not 'retry' in request.args:
        return redirect(request.url + ('&' if '?' in request.url else '?') + 'retry=1'), 307, {'cache-control': 'private,no-cache,must-revalidate,max-age=0'}
    return render_template('500.html'), 500

@app.errorhandler(400)
def error_400(body):
    return render_template('400.html'), 400

@app.errorhandler(403)
def error_403(body):
    return render_template('403.html'), 403

@app.errorhandler(404)
def error_404(body):
    return render_template('404.html'), 404

@app.errorhandler(405)
def error_405(body):
    return render_template('405.html'), 405

@app.errorhandler(451)
def error_451(body):
    return render_template('451.html'), 451

@app.errorhandler(500)
def error_500(body):
    g.no_user = True
    return render_template('500.html'), 500

@app.route('/favicon.ico')
def favicon_ico():
    return send_from_directory(APP_BASE_DIR, 'favicon.ico')

@app.route('/robots.txt')
def robots_txt():
    return send_from_directory(APP_BASE_DIR, 'robots.txt')


from .website import blueprints
for bp in blueprints:
    app.register_blueprint(bp)

from .ajax import bp
app.register_blueprint(bp)

from .rest import rest_bp
app.register_blueprint(rest_bp)




