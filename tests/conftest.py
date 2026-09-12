import asyncio

import pytest


@pytest.fixture
def click_ready():
    """Click once after mounting and layout make the requested widget clickable."""

    async def click(pilot, selector):
        async with asyncio.timeout(5):
            while not pilot.app.screen.query(selector):
                await pilot.pause(0.01)
            widget = pilot.app.screen.query_one(selector)
            while not (
                widget.region.width > 0
                and widget.region.height > 0
                and widget.region.center in pilot.app.screen.size.region
                and pilot.app.get_widget_at(*widget.region.center)[0] is widget
            ):
                await pilot.pause(0.01)
        assert await pilot.click(widget, offset=(widget.size.width // 2, widget.size.height // 2))

    return click
