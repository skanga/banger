import json

import httpx
import pytest

from banger.models import ModelClient, ModelConfig

TEXT = "café\u2028code\u0085end"


class FragmentedStream(httpx.AsyncByteStream):
    def __init__(self, text):
        self.data = text.encode("utf-8")

    async def __aiter__(self):
        for position in range(0, len(self.data), 2):
            yield self.data[position : position + 2]


def events(provider):
    if provider == "anthropic":
        return [
            {
                "type": "content_block_start",
                "index": 0,
                "content_block": {"type": "text", "text": TEXT},
            },
            {"type": "message_stop"},
        ]
    return [{"choices": [{"delta": {"content": TEXT}}]}, "[DONE]"]


@pytest.mark.parametrize("provider", ["openai", "anthropic"])
@pytest.mark.parametrize("newline", ["\n", "\r\n", "\r"])
async def test_multiline_events_with_bom_comments_and_fragmented_bytes(provider, newline):
    frames = []
    for event in events(provider):
        payload = (
            event if isinstance(event, str) else json.dumps(event, indent=2, ensure_ascii=False)
        )
        lines = ["data: " + part for part in payload.split("\n")]
        lines.extend(["event: message", "id: ignored", ": keepalive"])
        frames.append(newline.join(lines) + newline * 2)
    stream = "\ufeff" + "".join(frames)
    transport = httpx.MockTransport(lambda _: httpx.Response(200, stream=FragmentedStream(stream)))
    chunks = []
    async with ModelClient(
        ModelConfig(provider, "test", "http://localhost/v1"), transport
    ) as client:
        message = await client.generate("system", [], [], chunks.append)
    assert message == {"role": "assistant", "content": TEXT}
    assert chunks == [TEXT]


@pytest.mark.parametrize("provider", ["openai", "anthropic"])
async def test_unterminated_completion_event_is_not_accepted(provider):
    first, final = events(provider)
    end = final if isinstance(final, str) else json.dumps(final)
    stream = "data: " + json.dumps(first) + "\n\ndata: " + end + "\n"
    transport = httpx.MockTransport(lambda _: httpx.Response(200, text=stream))
    async with ModelClient(
        ModelConfig(provider, "test", "http://localhost/v1"), transport
    ) as client:
        with pytest.raises(RuntimeError, match="before completion"):
            await client.generate("system", [], [])
