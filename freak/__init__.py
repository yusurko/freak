

import logging
import re
from sqlite3 import ProgrammingError
import sys
from typing import Any
import warnings
from quart import (
    Quart, flash, g, jsonify, redirect, render_template,
    request, send_from_directory, url_for
)
import os
import dotenv
from quart_auth import AuthUser, QuartAuth, Action as QA_Action, current_user
from quart_wtf import CSRFProtect
from sqlalchemy import inspect, select
from suou import Snowflake, ssv_list
from werkzeug.routing import BaseConverter
from suou.sass import SassAsyncMiddleware
from suou.quart import negotiate
from hypercorn.middleware import ProxyFixMiddleware

from suou.configparse import ConfigOptions, ConfigValue
from suou import twocolon_list, WantsContentType

from .colors import color_themes, theme_classes

__version__ = '0.5.0-dev41'

APP_BASE_DIR = os.path.dirname(os.path.dirname(__file__))

if not dotenv.load_dotenv():
    warnings.warn('.env not loaded; application may break!', RuntimeWarning)

class AppConfig(ConfigOptions):
    secret_key = ConfigValue(required=True)
    database_url = ConfigValue(required=True)
    app_name = ConfigValue()
    server_name = ConfigValue()
    private_assets = ConfigValue(cast=ssv_list)
    # deprecated
    jquery_url = ConfigValue(default='https://ajax.googleapis.com/ajax/libs/jquery/3.7.1/jquery.min.js')
    app_is_behind_proxy = ConfigValue(cast=int, default=0)
    impressum = ConfigValue(cast=twocolon_list, default='')
    create_guild_threshold = ConfigValue(cast=int, default=15, prefix='freak_')

app_config = AppConfig()

logging.basicConfig(level=logging.WARNING)

logger = logging.getLogger(__name__)

app = Quart(__name__)
app.secret_key = app_config.secret_key
app.config['SQLALCHEMY_DATABASE_URI'] = app_config.database_url
app.config['JSONIFY_PRETTYPRINT_REGULAR'] = False
app.config['QUART_AUTH_DURATION'] = 365 * 24 * 60 * 60
app.config['SERVER_NAME'] = app_config.server_name


## DO NOT ADD LOCAL IMPORTS BEFORE THIS LINE

from .accounts import UserLoader
from .models import Guild, db, User, Post

# SASS
app.asgi_app = SassAsyncMiddleware(app.asgi_app, dict(
    freak=('static/sass', 'static/css', '/static/css', True)
))

# proxy fix
if app_config.app_is_behind_proxy:
    app.asgi_app = ProxyFixMiddleware(
        app.asgi_app, trusted_hops=app_config.app_is_behind_proxy, mode='legacy'
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

db.bind(app_config.database_url)

csrf = CSRFProtect(app)



    
# TODO configure quart_auth
login_manager = QuartAuth(app, user_class= UserLoader)

from . import filters


PRIVATE_ASSETS = os.getenv('PRIVATE_ASSETS', '').split()

post_count_cache = 0
user_count_cache = 0

@app.context_processor
async def _inject_variables():
    global post_count_cache, user_count_cache
    try:
        post_count = await Post.count()
        user_count = await User.active_count()
    except Exception as e:
        logger.error(f'cannot compute post_count: {e}')
        post_count = post_count_cache
        user_count = user_count_cache
    else:
        post_count_cache = post_count
        user_count_cache = user_count

    return {
        'app_name': app_config.app_name,
        'app_version': __version__,
        'server_name': app_config.server_name,
        'url_for_css': (lambda name, **kwargs: url_for('static', filename=f'css/{name}.css', **kwargs)),
        'private_scripts': [x for x in app_config.private_assets if x.endswith('.js')],
        'private_styles': [x for x in PRIVATE_ASSETS if x.endswith('.css')],
        'jquery_url': app_config.jquery_url,
        'post_count': post_count,
        'user_count': user_count,
        'colors': color_themes,
        'theme_classes': theme_classes,
        'impressum': '\n'.join(app_config.impressum).replace('_', ' ')
    }

@app.before_request
async def _load_user():
    try:
        await current_user._load()
    except RuntimeError as e:
        logger.error(f'{e}')
        g.no_user = True


@app.after_request
async def _unload_user(resp):
    try:
        await current_user._unload()
    except RuntimeError as e:
        logger.error(f'{e}')
    return resp


def redact_url_password(u: str | Any) -> str | Any:
    if not isinstance(u, str):
        return u
    return re.sub(r':[^@:/ ]+@', ':***@', u)

async def error_handler_for(status: int, message: str, template: str):
    match negotiate():
        case WantsContentType.JSON:
            return jsonify({'error': f'{message}', 'status': status}), status
        case WantsContentType.HTML:
            return await render_template(template, message=f'{message}'), status
        case WantsContentType.PLAIN:
            return f'{message} (HTTP {status})', status, {'content-type': 'text/plain; charset=UTF-8'}

@app.errorhandler(ProgrammingError)
async def error_db(body):
    g.no_user = True
    logger.error(f'No database access! (url is {redact_url_password(app.config['SQLALCHEMY_DATABASE_URI'])!r})', RuntimeWarning)
    return await error_handler_for(500, body, '500.html')

@app.errorhandler(400)
async def error_400(body):
    return await error_handler_for(400, body, '400.html')

@app.errorhandler(401)
async def error_401(body):
    match negotiate():
        case WantsContentType.HTML:
            return redirect(url_for('accounts.login', next=request.path))
        case _:
            return await error_handler_for(401, 'Please log in.', 'login.html')


@app.errorhandler(403)
async def error_403(body):
    return await error_handler_for(403, body, '403.html')

async def find_guild_or_user(name: str) -> str | None:
    """
    Used in 404 error handler.

    Returns an URL to redirect or None for no redirect.
    """

    if hasattr(g, 'no_user'):
        return None

    # do not execute for non-browsers_
    if 'Mozilla/' not in request.user_agent.string:
        return None

    async with db as session:
        gu = (await session.execute(select(Guild).where(Guild.name == name))).scalar()
        user = (await session.execute(select(User).where(User.username == name))).scalar()
    
        if gu is not None:
            await flash(f'There is nothing at /{name}. Luckily, a guild with name {gu.handle()} happens to exist. Next time, remember to add + before!')
            return gu.url()

        if user is not None:
            await flash(f'There is nothing at /{name}. Luckily, a user named {user.handle()} happens to exist. Next time, remember to add @ before!')
            return user.url()

        return None

@app.errorhandler(404)
async def error_404(body):
    try:
        if mo := re.match(r'/([a-z0-9_-]+)/?', request.path):
            alternative = await find_guild_or_user(mo.group(1))
            if alternative is not None:
                return redirect(alternative), 302
    except Exception as e:
        logger.error(f'Exception in find_guild_or_user: {e}')
        pass
    if app_config.server_name not in (None, request.host): 
        logger.warning(f'request host {request.host!r} is different from configured server name {app_config.server_name}')
        return redirect('//' + app_config.server_name + request.full_path), 307
    return await error_handler_for(404, 'Not found', '404.html')

@app.errorhandler(405)
async def error_405(body):
    return await error_handler_for(405, body, '405.html')

@app.errorhandler(451)
async def error_451(body):
    return await error_handler_for(451, body, '451.html')

@app.errorhandler(500)
async def error_500(body):
    g.no_user = True
    return await error_handler_for(500, body, '500.html')

@app.route('/favicon.ico')
async def favicon_ico():
    return await send_from_directory(APP_BASE_DIR, 'favicon.ico')

@app.route('/robots.txt')
async def robots_txt():
    return await send_from_directory(APP_BASE_DIR, 'robots.txt')


from .website import blueprints
for bp in blueprints:
    app.register_blueprint(bp)

from .ajax import bp
app.register_blueprint(bp)

from .rest import bp
app.register_blueprint(bp)




