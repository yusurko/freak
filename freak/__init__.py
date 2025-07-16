

import re
from sqlite3 import ProgrammingError
from typing import Any
import warnings
from flask import (
    Flask, g, redirect, render_template,
    request, send_from_directory, url_for
)
import os
import dotenv
from flask_login import LoginManager
from flask_wtf.csrf import CSRFProtect
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from suou import Snowflake, ssv_list
from werkzeug.routing import BaseConverter
from sassutils.wsgi import SassMiddleware
from werkzeug.middleware.proxy_fix import ProxyFix

from suou.configparse import ConfigOptions, ConfigValue

from .colors import color_themes, theme_classes
from .utils import twocolon_list

__version__ = '0.4.0-dev28'

APP_BASE_DIR = os.path.dirname(os.path.dirname(__file__))

if not dotenv.load_dotenv():
    warnings.warn('.env not loaded; application may break!', RuntimeWarning)

class AppConfig(ConfigOptions):
    secret_key = ConfigValue(required=True)
    database_url = ConfigValue(required=True)
    app_name = ConfigValue()
    domain_name = ConfigValue()
    private_assets = ConfigValue(cast=ssv_list)
    jquery_url = ConfigValue(default='https://ajax.googleapis.com/ajax/libs/jquery/3.7.1/jquery.min.js')
    app_is_behind_proxy = ConfigValue(cast=bool, default=False)
    impressum = ConfigValue(cast=twocolon_list, default=None)

app_config = AppConfig()

app = Flask(__name__)
app.secret_key = app_config.secret_key
app.config['SQLALCHEMY_DATABASE_URI'] = app_config.database_url
app.config['JSONIFY_PRETTYPRINT_REGULAR'] = False

from .models import db, User, Post

# SASS
app.wsgi_app = SassMiddleware(app.wsgi_app, dict(
    freak=('static/sass', 'static/css', '/static/css', True)
))

# proxy fix
if app_config.app_is_behind_proxy:
    app.wsgi_app = ProxyFix(
        app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1
    )

class SlugConverter(BaseConverter):
    regex = r'[a-z0-9]+(?:-[a-z0-9]+)*'

class B32lConverter(BaseConverter):
    regex = r'_?[a-z2-7]+'
    def to_url(self, value):
        return Snowflake(value).to_b32l()
    def to_python(self, value):
        return Snowflake.from_b32l(value)

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
        'app_name': app_config.app_name,
        'app_version': __version__,
        'domain_name': app_config.domain_name,
        'url_for_css': (lambda name, **kwargs: url_for('static', filename=f'css/{name}.css', **kwargs)),
        'private_scripts': [x for x in app_config.private_assets if x.endswith('.js')],
        'private_styles': [x for x in PRIVATE_ASSETS if x.endswith('.css')],
        'jquery_url': app_config.jquery_url,
        'post_count': Post.count(),
        'user_count': User.active_count(),
        'colors': color_themes,
        'theme_classes': theme_classes,
        'impressum': '\n'.join(app_config.impressum).replace('_', ' ')
    }

@login_manager.user_loader
def _inject_user(userid):
    try:
        u = db.session.execute(select(User).where(User.id == userid)).scalar()
        if u is None or u.is_disabled:
            return None
        return u
    except SQLAlchemyError as e:
        warnings.warn(f'cannot retrieve user {userid} from db (exception: {e})', RuntimeWarning)
        g.no_user = True
        return None

def redact_url_password(u: str | Any) -> str | Any:
    if not isinstance(u, str):
        return u
    return re.sub(r':[^@:/ ]+@', ':***@', u)

@app.errorhandler(ProgrammingError)
def error_db(body):
    g.no_user = True
    warnings.warn(f'No database access! (url is {redact_url_password(app.config['SQLALCHEMY_DATABASE_URI'])!r})', RuntimeWarning)
    return render_template('500.html'), 500

@app.errorhandler(400)
def error_400(body):
    return render_template('400.html'), 400

@app.errorhandler(403)
def error_403(body):
    return render_template('403.html'), 403

from .search import find_guild_or_user

@app.errorhandler(404)
def error_404(body):
    try:
        if mo := re.match(r'/([a-z0-9_-]+)/?', request.path):
            alternative = find_guild_or_user(mo.group(1))
            if alternative is not None:
                return redirect(alternative), 302
    except Exception as e:
        warnings.warn(f'Exception in find_guild_or_user: {e}')
        pass
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




