import pytest
from textual.widgets import Input, ListView, RichLog, Select

from banger.app import AgentEvent, BangerApp


@pytest.mark.parametrize("restored", [False, True])
async def test_chat_headings_remain_legible_and_formatted(tmp_path, click_ready, restored):
    app = BangerApp(tmp_path)
    content = "\n\n".join("#" * level + f" Heading{level}" for level in range(1, 7))
    async with app.run_test(size=(120, 40)) as pilot:
        app.screen.query_one("#model", Input).value = "fixture-model"
        app.screen.query_one("#mode", Select).value = "read-only"
        await click_ready(pilot, "#start")
        await pilot.pause()
        if restored:
            session = app.agent.session
            app.state.append(session, {"role": "assistant", "content": content})
            await pilot.press("ctrl+n")
            await click_ready(pilot, "#--content-tab-sessions-tab")
            listing = app.query_one("#sessions", ListView)
            listing.index = app.session_ids.index(session)
            listing.focus()
            await pilot.press("enter")
        else:
            app.on_agent_event(AgentEvent("done", content))
        await pilot.pause()
        log = app.query_one("#chat-log", RichLog)
        for level in range(1, 7):
            segments = [
                segment
                for line in log.lines
                for segment in line
                if f"Heading{level}" in segment.text
            ]
            assert segments, level
            for segment in segments:
                assert "#" not in segment.text, (
                    "Restored Markdown must be rendered, not shown as raw syntax"
                )
                style = segment.style
                assert style and not style.dim, (level, style)
                color = style.color.get_truecolor() if style.color else (213, 225, 232)

                # Relative luminance of the actual rendered foreground over the dark chat surface.
                def luminance(rgb):
                    channels = [v / 255 for v in rgb]
                    linear = [
                        v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4
                        for v in channels
                    ]
                    return sum(
                        v * weight
                        for v, weight in zip(linear, (0.2126, 0.7152, 0.0722), strict=True)
                    )

                assert (luminance(color) + 0.05) / (luminance((17, 24, 32)) + 0.05) >= 4.5, (
                    level,
                    style,
                )
