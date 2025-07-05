
import markdown
from markupsafe import Markup

from suou import Siq, Snowflake
from suou.markdown import StrikethroughExtension, SpoilerExtension, PingExtension

from . import app

# make spoilers prevail over blockquotes
SpoilerExtension.patch_blockquote_processor()

@app.template_filter()
def to_markdown(text, toc = False):
    extensions = [
        'tables', 'footnotes', 'fenced_code', 'sane_lists',
        StrikethroughExtension(), SpoilerExtension(),
        PingExtension({'@': '/@', '+': '/+'})
    ]
    if toc:
        extensions.append('toc')
    return Markup(markdown.Markdown(extensions=extensions).convert(text))

app.template_filter('markdown')(to_markdown)

@app.template_filter()
def to_b32l(n):
    return Snowflake(n).to_b32l()

app.template_filter('b32l')(to_b32l)

@app.template_filter()
def to_cb32(n):
    return '0' + Siq.from_bytes(n).to_cb32()

app.template_filter('cb32')(to_cb32)

@app.template_filter()
def append(text, l: list):
    l.append(text)
    return None

