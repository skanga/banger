import json

import httpx
import pytest

from banger.models import ModelClient, ModelConfig


@pytest.mark.parametrize("provider", ["anthropic", "openai"])
async def test_tool_roundtrip_and_auth(provider):
    requests = []

    def respond(request):
        requests.append(json.loads(request.content))
        if provider == "anthropic":
            assert request.headers["x-api-key"] == "test-secret"
            assert request.url.path == "/v1/messages"
            return httpx.Response(
                200,
                json={
                    "content": [
                        {
                            "type": "tool_use",
                            "id": "call1",
                            "name": "read_file",
                            "input": {"path": "a.py"},
                        }
                    ],
                    "stop_reason": "tool_use",
                },
            )
        assert request.headers["authorization"] == "Bearer test-secret"
        assert request.url.path == "/v1/chat/completions"
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "content": None,
                            "tool_calls": [
                                {
                                    "id": "call1",
                                    "type": "function",
                                    "function": {
                                        "name": "read_file",
                                        "arguments": '{"path":"a.py"}',
                                    },
                                }
                            ],
                        }
                    }
                ]
            },
        )

    config = ModelConfig(
        provider=provider,
        model="test-model",
        base_url="https://example.test/v1",
        api_key="test-secret",
        stream=False,
    )
    async with ModelClient(config, transport=httpx.MockTransport(respond)) as client:
        first = await client.generate("system", [{"role": "user", "content": "inspect"}], [])
        assert first["tool_calls"][0]["function"]["name"] == "read_file"
        await client.generate(
            "system",
            [
                {"role": "user", "content": "inspect"},
                first,
                {"role": "tool", "tool_call_id": "call1", "content": "source"},
            ],
            [],
        )
    last = requests[-1]["messages"][-1]
    assert last["role"] == ("user" if provider == "anthropic" else "tool")
    if provider == "anthropic":
        assert last["content"][0]["tool_use_id"] == "call1"


async def test_openai_stream_assembles_fragmented_tool_arguments():
    events = [
        {
            "choices": [
                {
                    "delta": {
                        "content": "Looking",
                        "tool_calls": [
                            {
                                "index": 0,
                                "id": "x",
                                "function": {"name": "read_file", "arguments": '{"pa'},
                            }
                        ],
                    }
                }
            ]
        },
        {
            "choices": [
                {"delta": {"tool_calls": [{"index": 0, "function": {"arguments": 'th":"a.py"}'}}]}}
            ]
        },
    ]
    stream = "".join("data: " + json.dumps(e) + "\n\n" for e in events) + "data: [DONE]\n\n"
    transport = httpx.MockTransport(
        lambda _: httpx.Response(200, text=stream, headers={"content-type": "text/event-stream"})
    )
    chunks = []
    async with ModelClient(
        ModelConfig("openai", "local", "http://localhost/v1"), transport
    ) as client:
        message = await client.generate("system", [], [], chunks.append)
    assert chunks == ["Looking"]
    assert json.loads(message["tool_calls"][0]["function"]["arguments"]) == {"path": "a.py"}


async def test_anthropic_stream_collects_text_and_tools():
    events = [
        {"type": "content_block_start", "index": 0, "content_block": {"type": "text", "text": ""}},
        {
            "type": "content_block_delta",
            "index": 0,
            "delta": {"type": "text_delta", "text": "Inspect"},
        },
        {
            "type": "content_block_start",
            "index": 1,
            "content_block": {"type": "tool_use", "id": "x", "name": "read_file", "input": {}},
        },
        {
            "type": "content_block_delta",
            "index": 1,
            "delta": {"type": "input_json_delta", "partial_json": '{"path":"a.py"}'},
        },
        {"type": "message_stop"},
    ]
    transport = httpx.MockTransport(
        lambda _: httpx.Response(
            200, text="".join("data: " + json.dumps(e) + "\n\n" for e in events)
        )
    )
    async with ModelClient(
        ModelConfig("anthropic", "test", "https://example.test/v1", "key"), transport
    ) as client:
        message = await client.generate("system", [], [])
    assert message["content"] == "Inspect"
    assert json.loads(message["tool_calls"][0]["function"]["arguments"]) == {"path": "a.py"}


@pytest.mark.parametrize("provider", ["openai", "anthropic"])
async def test_truncated_generation_is_not_accepted_as_a_complete_action(provider):
    if provider == "openai":
        data = {
            "choices": [
                {
                    "finish_reason": "length",
                    "message": {"role": "assistant", "content": "Incomplete"},
                }
            ]
        }
    else:
        data = {"stop_reason": "max_tokens", "content": [{"type": "text", "text": "Incomplete"}]}
    transport = httpx.MockTransport(lambda _: httpx.Response(200, json=data))
    config = ModelConfig(provider, "test", "https://example.test/v1", "key", stream=False)
    async with ModelClient(config, transport) as client:
        with pytest.raises(RuntimeError, match="limit"):
            await client.generate("system", [], [])


async def test_openai_completion_token_parameter_compatibility():
    bodies = []

    def respond(request):
        body = json.loads(request.content)
        bodies.append(body)
        if "max_tokens" in body:
            return httpx.Response(
                400, json={"error": {"param": "max_tokens", "code": "unsupported_parameter"}}
            )
        return httpx.Response(
            200, json={"choices": [{"message": {"role": "assistant", "content": "OK"}}]}
        )

    config = ModelConfig("openai", "test", "https://example.test/v1", stream=False)
    async with ModelClient(config, httpx.MockTransport(respond)) as client:
        assert (await client.generate("system", [], []))["content"] == "OK"
    assert bodies[1]["max_completion_tokens"] == config.max_tokens


async def test_incomplete_stream_does_not_return_tool_calls():
    event = {
        "choices": [
            {
                "delta": {
                    "tool_calls": [
                        {
                            "index": 0,
                            "id": "x",
                            "function": {"name": "delete_file", "arguments": '{"path":"a.py"}'},
                        }
                    ]
                }
            }
        ]
    }
    transport = httpx.MockTransport(
        lambda _: httpx.Response(200, text="data: " + json.dumps(event) + "\n\n")
    )
    async with ModelClient(
        ModelConfig("openai", "test", "http://localhost/v1"), transport
    ) as client:
        with pytest.raises(RuntimeError, match="before completion"):
            await client.generate("system", [], [])
