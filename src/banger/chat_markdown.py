"""Markdown styles suited to Banger's dark chat surface."""

from rich.markdown import Markdown
from rich.theme import Theme

HEADINGS = Theme(
    {
        f"markdown.h{level}": "#d5e1e8 not dim " + style
        for level, style in enumerate(
            ("bold underline", "bold underline", "bold", "bold italic", "italic", "italic"),
            start=1,
        )
    }
)


class ChatMarkdown(Markdown):
    def __rich_console__(self, console, options):
        with console.use_theme(HEADINGS):
            yield from super().__rich_console__(console, options)
