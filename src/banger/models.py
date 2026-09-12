"""Provider adapters with a shared, persisted tool-call message format."""

import asyncio
import json
from dataclasses import dataclass

import httpx


async def event_lines(response):
    """SSE uses UTF-8 and CR/LF boundaries, not Unicode splitlines boundaries."""
    response.encoding = "utf-8"
    line, carriage_return = [], False
    async for chunk in response.aiter_text():
        for character in chunk:
            if character == "\n" and carriage_return:
                carriage_return = False
                continue
            carriage_return = character == "\r"
            if character in "\r\n":
                yield "".join(line)
                line = []
            else:
                line.append(character)


async def event_data(response):
    """Assemble SSE data fields; an unfinished event at EOF is discarded."""
    data, first = [], True
    async for line in event_lines(response):
        if first:
            line = line.removeprefix("\ufeff")
            first = False
        if not line:
            if data:
                yield "\n".join(data)
                data = []
            continue
        field, _, value = line.partition(":")
        if field == "data":
            data.append(value.removeprefix(" "))


@dataclass
class ModelConfig:
    provider: str
    model: str
    base_url: str
    api_key: str = ""
    stream: bool = True
    max_tokens: int = 8192


class ModelClient:
    def __init__(self, config, transport=None):
        self.config = config
        if config.provider not in {"anthropic", "openai"}:
            raise ValueError("Provider must be anthropic or openai")
        self.client = httpx.AsyncClient(
            transport=transport or httpx.AsyncHTTPTransport(retries=2), timeout=120
        )
        self.usage = {}
        self.token_parameter = "max_tokens"

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        await self.client.aclose()

    def _anthropic_messages(self, messages):
        converted = []
        for message in messages:
            role = message["role"]
            if role == "tool":
                role = "user"
                blocks = [
                    {
                        "type": "tool_result",
                        "tool_use_id": message["tool_call_id"],
                        "content": message["content"],
                    }
                ]
            else:
                blocks = []
                if message.get("content"):
                    blocks.append({"type": "text", "text": message["content"]})
                for call in message.get("tool_calls", []):
                    blocks.append(
                        {
                            "type": "tool_use",
                            "id": call["id"],
                            "name": call["function"]["name"],
                            "input": json.loads(call["function"]["arguments"]),
                        }
                    )
            if not blocks:
                continue
            if converted and converted[-1]["role"] == role:
                converted[-1]["content"].extend(blocks)
            else:
                converted.append({"role": role, "content": blocks})
        return converted

    async def generate(self, system, messages, tools, on_text=None):
        config = self.config
        anthropic = config.provider == "anthropic"
        body = {
            "model": config.model,
            "stream": config.stream,
            self.token_parameter: config.max_tokens,
        }
        if anthropic:
            body.update(system=system, messages=self._anthropic_messages(messages))
            if tools:
                body["tools"] = tools
            headers = {"x-api-key": config.api_key, "anthropic-version": "2023-06-01"}
            endpoint = "messages"
        else:
            body["messages"] = [{"role": "system", "content": system}] + messages
            if tools:
                body["tools"] = [
                    {
                        "type": "function",
                        "function": {
                            "name": t["name"],
                            "description": t["description"],
                            "parameters": t["input_schema"],
                        },
                    }
                    for t in tools
                ]
            headers = {"Authorization": "Bearer " + config.api_key} if config.api_key else {}
            endpoint = "chat/completions"
        url = config.base_url.rstrip("/") + "/" + endpoint
        for attempt in range(3):
            async with self.client.stream("POST", url, json=body, headers=headers) as response:
                if (
                    response.status_code == 400
                    and not anthropic
                    and "max_tokens" in body
                    and attempt < 2
                ):
                    data = json.loads(await response.aread())
                    error = data.get("error", {})
                    if (
                        error.get("param") == "max_tokens"
                        and error.get("code") == "unsupported_parameter"
                    ):
                        self.token_parameter = "max_completion_tokens"
                        body[self.token_parameter] = body.pop("max_tokens")
                        continue
                if response.status_code in {429, 500, 502, 503, 504} and attempt < 2:
                    await response.aread()
                    await asyncio.sleep(2**attempt)
                    continue
                response.raise_for_status()
                if not config.stream:
                    data = json.loads(await response.aread())
                    reason = (
                        data.get("stop_reason")
                        if anthropic
                        else data.get("choices", [{}])[0].get("finish_reason")
                    )
                    if reason in {"length", "max_tokens"}:
                        raise RuntimeError(
                            "Model output limit reached; response was incomplete and no tools were executed"
                        )
                    self.usage = data.get("usage", {})
                    if anthropic:
                        message = {"role": "assistant", "content": "", "tool_calls": []}
                        for block in data["content"]:
                            if block["type"] == "text":
                                message["content"] += block["text"]
                            elif block["type"] == "tool_use":
                                message["tool_calls"].append(
                                    self._call(
                                        block["id"], block["name"], json.dumps(block["input"])
                                    )
                                )
                    else:
                        raw = data["choices"][0]["message"]
                        message = {
                            k: v for k, v in raw.items() if k in {"role", "content", "tool_calls"}
                        }
                    if on_text and message.get("content"):
                        on_text(message["content"])
                    return message
                return await self._stream(response, anthropic, on_text)
        raise RuntimeError("Model retry limit reached")

    @staticmethod
    def _call(identity, name, arguments):
        return {
            "id": identity,
            "type": "function",
            "function": {"name": name, "arguments": arguments},
        }

    async def _stream(self, response, anthropic, on_text):
        content, calls = [], {}
        finished = False
        async for payload in event_data(response):
            if payload == "[DONE]":
                finished = True
                break
            event = json.loads(payload)
            chunk = ""
            if anthropic:
                kind = event.get("type")
                if kind == "error":
                    raise RuntimeError(
                        "Provider stream error: " + str(event.get("error", {}).get("type"))
                    )
                if kind == "message_stop":
                    finished = True
                elif kind == "content_block_start":
                    block = event["content_block"]
                    if block["type"] == "tool_use":
                        calls[event["index"]] = self._call(block["id"], block["name"], "")
                    elif block["type"] == "text":
                        chunk = block.get("text", "")
                elif kind == "content_block_delta":
                    delta = event["delta"]
                    if delta["type"] == "text_delta":
                        chunk = delta["text"]
                    elif delta["type"] == "input_json_delta":
                        calls[event["index"]]["function"]["arguments"] += delta["partial_json"]
                elif (
                    kind == "message_delta"
                    and event.get("delta", {}).get("stop_reason") == "max_tokens"
                ):
                    raise RuntimeError("Model output limit reached; no tools were executed")
                if "usage" in event:
                    self.usage.update(event["usage"])
                if "message" in event:
                    self.usage.update(event["message"].get("usage", {}))
            else:
                if event.get("error"):
                    raise RuntimeError("Provider stream error")
                if event.get("usage"):
                    self.usage = event["usage"]
                for choice in event.get("choices", []):
                    if choice.get("finish_reason") == "length":
                        raise RuntimeError("Model output limit reached; no tools were executed")
                    delta = choice.get("delta", {})
                    chunk += delta.get("content") or ""
                    for fragment in delta.get("tool_calls", []):
                        call = calls.setdefault(fragment["index"], self._call("", "", ""))
                        if fragment.get("id"):
                            call["id"] = fragment["id"]
                        for field in ("name", "arguments"):
                            call["function"][field] += fragment.get("function", {}).get(field, "")
            if chunk:
                content.append(chunk)
                if on_text:
                    on_text(chunk)
        if not finished:
            raise RuntimeError("Provider stream ended before completion; no tools were executed")
        message = {"role": "assistant", "content": "".join(content)}
        if calls:
            message["tool_calls"] = [calls[i] for i in sorted(calls)]
            for call in message["tool_calls"]:
                if not call["function"]["arguments"]:
                    call["function"]["arguments"] = "{}"
                json.loads(call["function"]["arguments"])
        return message
