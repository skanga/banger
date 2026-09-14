import pytest
from textual.widgets import Input, Select

from banger.app import BangerApp
from banger.permissions import Mode


def saved_config(**changes):
    return {
        "provider": "openai",
        "model": "local-model",
        "base_url": "http://localhost:1234/v1",
        "mode": "ask",
        "shell": "bash",
        "stronger_model": "",
        **changes,
    }


@pytest.mark.parametrize("mode", list(Mode))
async def test_saved_configuration_starts_without_setup(tmp_path, monkeypatch, mode):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    app = BangerApp(tmp_path)
    app.state.put_artifact("config", "last", saved_config(mode=mode.value))
    async with app.run_test() as pilot:
        await pilot.pause()
        assert app.screen.id != "setup"
        assert app.agent.tools.policy.mode is mode
        assert app.client.config.model == "local-model"
        app.set_mode(Mode.READ_ONLY)
        assert app.state.artifact("config", "last")["mode"] == "read-only"
    restarted = BangerApp(tmp_path)
    async with restarted.run_test() as pilot:
        await pilot.pause()
        assert restarted.agent.tools.policy.mode is Mode.READ_ONLY


@pytest.mark.parametrize("provider", ["openai", "anthropic"])
async def test_saved_configuration_uses_environment_key(tmp_path, monkeypatch, provider):
    monkeypatch.setenv(provider.upper() + "_API_KEY", "environment-key")
    app = BangerApp(tmp_path)
    app.state.put_artifact("config", "last", saved_config(provider=provider, requires_api_key=True))
    async with app.run_test() as pilot:
        await pilot.pause()
        assert app.screen.id != "setup"
        assert app.client.config.api_key == "environment-key"
        assert "api_key" not in app.state.artifact("config", "last")


@pytest.mark.parametrize(
    "settings",
    [
        {"requires_api_key": True},
        {"base_url": "https://api.openai.com/v1"},
        {"provider": "anthropic", "base_url": "https://api.anthropic.com/v1"},
    ],
)
async def test_missing_key_reopens_setup_with_saved_permissions(tmp_path, monkeypatch, settings):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    app = BangerApp(tmp_path)
    app.state.put_artifact("config", "last", saved_config(mode="accept-edits", **settings))
    async with app.run_test() as pilot:
        await pilot.pause()
        assert app.screen.id == "setup"
        assert app.screen.query_one("#mode", Select).value == "accept-edits"


async def test_typed_key_is_not_saved_but_required_on_restart(tmp_path, monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    app = BangerApp(tmp_path)
    async with app.run_test(size=(120, 40)) as pilot:
        app.screen.query_one("#model", Input).value = "model"
        app.screen.query_one("#mode", Select).value = "ask"
        app.screen.query_one("#api-key", Input).value = "typed-key"
        await pilot.click("#start")
        await pilot.pause()
        saved = app.state.artifact("config", "last")
        assert saved["requires_api_key"] is True
        assert "typed-key" not in str(saved)
    restarted = BangerApp(tmp_path)
    async with restarted.run_test() as pilot:
        await pilot.pause()
        assert restarted.screen.id == "setup"
        assert restarted.screen.query_one("#mode", Select).value == "ask"


async def test_setup_can_be_explicitly_reopened(tmp_path):
    app = BangerApp(tmp_path, setup=True)
    app.state.put_artifact("config", "last", saved_config())
    async with app.run_test() as pilot:
        await pilot.pause()
        assert app.screen.id == "setup"
        assert app.screen.query_one("#mode", Select).value == "ask"


async def test_incomplete_saved_configuration_still_requires_setup(tmp_path):
    app = BangerApp(tmp_path)
    app.state.put_artifact("config", "last", saved_config(mode=""))
    async with app.run_test() as pilot:
        await pilot.pause()
        assert app.screen.id == "setup"
        assert app.screen.query_one("#mode", Select).value is Select.NULL
