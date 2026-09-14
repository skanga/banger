# Banger

Banger is a terminal coding agent for inspecting projects, making guarded source edits, running commands and tests, and resuming saved conversations. It works with Anthropic and OpenAI-compatible endpoints, including local servers that support tool calling.

## Install

Banger requires Python 3.11 or later and runs on Windows, Linux, and macOS. Install Git when working in a Git repository. You do not need to clone Banger to use it.

### With uv (recommended)

Install [uv](https://docs.astral.sh/uv/getting-started/installation/), then install Banger in its own environment:

```console
uv tool install https://github.com/skanga/banger/releases/download/v0.1.0/banger-0.1.0-py3-none-any.whl
banger
```

If `banger` is not found, run `uv tool update-shell` and open a new terminal. See [uv's tool guide](https://docs.astral.sh/uv/guides/tools/) for managing installed applications.

### With pip

Create a virtual environment:

```console
python -m venv .venv-banger
```

Activate it on Linux or macOS:

```sh
source .venv-banger/bin/activate
```

Or activate it in Windows PowerShell:

```powershell
.\.venv-banger\Scripts\Activate.ps1
```

Then install and run Banger:

```console
python -m pip install https://github.com/skanga/banger/releases/download/v0.1.0/banger-0.1.0-py3-none-any.whl
banger
```

Use `python3` or `py` instead of `python` if needed to select Python 3.11+. Reactivate this environment in subsequent terminals. If activation is unavailable, run its interpreter directly, for example `.\.venv-banger\Scripts\python.exe -m banger` on Windows.

These commands use [pip's archive installation support](https://pip.pypa.io/en/stable/cli/pip_install/) and the published [GitHub release](https://github.com/skanga/banger/releases/tag/v0.1.0). Use the release URL rather than a bare `pip install banger` or `uv tool install banger`; this project is distributed through GitHub Releases.

### Upgrade or uninstall

To upgrade, copy the wheel URL from the desired [release](https://github.com/skanga/banger/releases) and run `uv tool install --upgrade <wheel-url>` or, in your pip environment, `python -m pip install --upgrade <wheel-url>`.

To uninstall, run `uv tool uninstall banger` or `python -m pip uninstall banger`, matching your installation method. Uninstalling the application does not remove your projects' saved conversations.

## Start a project

Run Banger from your project directory, or pass the directory explicitly:

```console
banger /path/to/project
```

On Windows, quote paths containing spaces: `banger "C:\Users\you\My Project"`.

On first launch, choose a provider, model ID, API base URL, shell, and permission mode. Local OpenAI-compatible servers must support Chat Completions tool calling. Use the provider's exact model ID and an API base URL including the API prefix, usually `/v1`.

Enter an API key in the masked field or supply `OPENAI_API_KEY` / `ANTHROPIC_API_KEY` in the environment. Local endpoints can leave the key blank. Typed keys stay in memory and must be entered again after restarting; environment keys are read on startup. Banger does not load `.env` files automatically.

Settings, including permission changes, are remembered per project. Setup is skipped when the configuration is complete and any required key is available. Reopen it with:

```console
banger --setup /path/to/project
```

The first source query downloads the language grammars it needs; later queries reuse the cache. Model requests require access to the configured endpoint.

## Use Banger

Enter a task in Chat and press Enter. For example:

> Find the entry point and explain how requests reach the database. Do not change files.

Or ask for a coding task:

> Find why the login test fails, propose a fix, and run the relevant tests after applying it.

| Control | Use |
|---|---|
| File tree / Source | Browse and read files; additions, deletions, and renames refresh automatically. |
| Chat | Send tasks and read streaming responses. |
| Diffs | Review changes made through Banger's edit tools. |
| Tools | Inspect tool inputs, results, command output, and errors. |
| Sessions | Select a saved conversation to resume it. |
| Escape | Interrupt the current task or deny an approval dialog. |
| Ctrl+P | Change and save the project's permission mode. |
| Ctrl+N | Start a new conversation and clear remembered action approvals. |
| Ctrl+L | Focus the prompt. |
| Ctrl+Q | Quit. |

An animated **Working** indicator appears in the status bar and terminal title. Pending approvals show **Action required** and ring the terminal bell once. Title and bell behavior depend on terminal settings.

## Choose permissions

| Mode | Project reads | Project edits | Commands |
|---|---|---|---|
| Read-only | Automatic | Denied | Denied |
| Ask | Automatic | Ask | Ask |
| Accept-edits | Automatic | Automatic | Ask |
| Full-access | Automatic | Automatic | Automatic |

Access outside the project requires approval except in full-access mode; read-only mode still denies all edits and commands. Switching to an optional stronger model always requires confirmation.

Commands run on your host with its filesystem and network access. Permission prompts do not provide a sandbox. Review approval details before allowing changes or execution.

## Learn more

The [user guide](docs/USER_GUIDE.md) covers model setup, approvals, editing and undo, supported languages, saved sessions, tracing, and troubleshooting.

## Run from source

From a checkout of this repository:

```console
uv sync --locked
uv run banger /path/to/project
```
