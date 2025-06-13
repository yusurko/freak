
import re, markdown
from markdown.inlinepatterns import InlineProcessor, SimpleTagInlineProcessor
import xml.etree.ElementTree as etree
from markupsafe import Markup


from . import app

from .iding import id_to_b32l

#### MARKDOWN EXTENSIONS ####

class StrikethroughExtension(markdown.extensions.Extension):
    def extendMarkdown(self, md: markdown.Markdown, md_globals=None):
        postprocessor = StrikethroughPostprocessor(md)
        md.postprocessors.register(postprocessor, 'strikethrough', 0)

class StrikethroughPostprocessor(markdown.postprocessors.Postprocessor):
    pattern = re.compile(r"~~(((?!~~).)+)~~", re.DOTALL)

    def run(self, html):
        return re.sub(self.pattern, self.convert, html)

    def convert(self, match):
        return '<del>' + match.group(1) + '</del>'


### XXX it currently only detects spoilers that are not at the beginning of the line. To be fixed.
class SpoilerExtension(markdown.extensions.Extension):
    def extendMarkdown(self, md: markdown.Markdown, md_globals=None):
        md.inlinePatterns.register(SimpleTagInlineProcessor(r'()>!(.*?)!<', 'span class="spoiler"'), 'spoiler', 14)

    @classmethod
    def patch_blockquote_processor(cls):
        """Patch BlockquoteProcessor to make Spoiler prevail over blockquotes."""
        from markdown.blockprocessors import BlockQuoteProcessor
        BlockQuoteProcessor.RE = re.compile(r'(^|\n)[ ]{0,3}>(?!!)[ ]?(.*)')

#  make spoilers prevail over blockquotes
SpoilerExtension.patch_blockquote_processor()

class MentionPattern(InlineProcessor):
    def __init__(self, regex, url_prefix: str):
        super().__init__(regex)
        self.url_prefix = url_prefix
    def handleMatch(self, m, data):
        el = etree.Element('a')
        el.attrib['href'] = self.url_prefix + m.group(1)
        el.text = m.group(0)
        return el, m.start(0), m.end(0)

class PingExtension(markdown.extensions.Extension):
    def extendMarkdown(self, md: markdown.Markdown, md_globals=None):
        md.inlinePatterns.register(MentionPattern(r'@([a-zA-Z0-9_-]{2,32})', '/@'), 'ping_mention', 14)
        md.inlinePatterns.register(MentionPattern(r'\+([a-zA-Z0-9_-]{2,32})', '/+'), 'ping_mention', 14)

@app.template_filter()
def to_markdown(text, toc = False):
    extensions = [
        'tables', 'footnotes', 'fenced_code', 'sane_lists',
        StrikethroughExtension(), SpoilerExtension(),
        ## XXX untested
        PingExtension()
    ]
    if toc:
        extensions.append('toc')
    return Markup(markdown.Markdown(extensions=extensions).convert(text))

@app.template_filter()
def to_b32l(n):
    return id_to_b32l(n)


@app.template_filter()
def append(text, l):
    l.append(text)
    return None
