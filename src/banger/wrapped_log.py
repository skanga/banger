"""Wrapped terminal output that reflows when its pane becomes visible or resizes."""

from rich.text import Text
from textual.widgets import RichLog


class WrappedLog(RichLog):
    DEFAULT_CSS = "WrappedLog { scrollbar-gutter: stable; }"

    def __init__(self, **kwargs):
        super().__init__(wrap=True, min_width=1, **kwargs)
        self._entries = []
        self._render_width = 0
        self._dirty = False

    def write(self, content):
        content = content.copy() if isinstance(content, Text) else content
        self._entries.append(content)
        if self.size.width and self._render_width:
            super().write(content, width=self._render_width)
        else:
            self._dirty = True
        return self

    def on_resize(self, event):
        event.prevent_default()
        super().on_resize(event)
        if not event.size.width:
            return
        width = max(1, event.size.width - self.scrollbar_size_vertical)
        if width != self._render_width or self._dirty:
            at_end = self.scroll_y >= self.max_scroll_y
            scroll_y = self.scroll_y
            self._render_width = width
            self._dirty = False
            super().clear()
            for entry in self._entries:
                super().write(entry, width=width, scroll_end=False)
            if at_end:
                self.scroll_end(animate=False, x_axis=False)
            else:
                self.scroll_to(y=scroll_y, animate=False)

    def clear(self):
        self._entries.clear()
        self._dirty = False
        return super().clear()
