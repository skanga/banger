# Banger

Banger is an independent Python coding agent with a terminal UI, structured code queries, guarded edits, persistent project state, and local command execution. It uses uv and does not require VS Code. Neither the Benzi implementation nor mini-swe-agent code is included in Banger.

## Run

From this directory:

```console
uv sync --locked
uv run banger
```

To work on another repository:

```console
uv run banger /path/to/project
```

On Windows, pass a Windows path, quoting it if it contains spaces. Python 3.11 or later is required. The first source-indexing run downloads the required tree-sitter grammars into the language pack's user cache; subsequent runs use that cache. Model requests still need access to the configured endpoint.

Banger constrains tree-sitter to the 0.25 series: 0.26.0 produced native crashes on a larger indexing fixture. Keep the packaged dependency constraint when installing; the regression and verification details are recorded in `docs/FEATURE_AUDIT.md`.

The setup screen asks for a provider, model ID, API base URL, optional stronger model, shell, and permission mode. Choose Anthropic or an OpenAI-compatible service, including a local server that supports Chat Completions tool calling. Use the provider's exact model ID. Base URLs include the API prefix, typically `/v1`.

API keys can be entered in the masked setup field or supplied through `ANTHROPIC_API_KEY` / `OPENAI_API_KEY`. A local endpoint may leave the key blank. Keys entered in setup stay in memory and are not saved in configuration or conversation history. After restarting, enter the key again or use an environment variable.

## Terminal workflow

- **Chat:** enter a task and press Enter. Responses stream while the agent works.
- **Source:** select a file in the left-hand tree to inspect it.
- **Diffs:** inspect changes produced by the edit tools.
- **Tools:** inspect tool arguments, results, errors, and command output.
- **Sessions:** select a saved conversation to resume it.
- **Escape:** interrupt the current task. Pending actions are marked as interrupted rather than automatically replayed.
- **Ctrl+P:** change permission mode while retaining the current model connection.
- **Ctrl+N:** start another conversation; remembered action approvals are cleared.
- **Ctrl+L:** focus the chat prompt. **Ctrl+Q:** exit.

The UI supports keyboard and mouse navigation. Integrated source editing and a graph view are not part of this version.

An [exported TUI preview](docs/tui-preview.svg) comes from the automated interaction test with deterministic model responses, not a live model session.

## Permissions and execution

| Mode | Project reads | File changes | Commands |
|---|---|---|---|
| Read-only | Automatic | Denied | Denied |
| Ask | Automatic | Ask | Ask |
| Accept-edits | Automatic | Automatic within the project | Ask |
| Full-access | Automatic | Automatic | Automatic |

Built-in file access outside the project asks for approval except in full-access mode. Approvals can be remembered for an exact command and working directory during the session. Remembering a command does not approve an expanded command or a different directory. Model escalation always requires confirmation, including in full-access mode.

These modes follow the familiar separation between action approval and isolation described in [Claude Code's permission documentation](https://code.claude.com/docs/en/permission-modes). **Commands execute on the host with filesystem and network access.** Permission prompts do not constitute a sandbox. Container execution is deferred to a later version.

Native Windows execution uses cmd, and Linux/macOS execution uses bash. Bash can also be selected on Windows when a functioning bash installation is available on PATH. Commands run independently in the selected working directory; shell state does not persist between calls. Output is bounded, commands have timeouts, and cancellation terminates their process tree. Windows runners use [job objects](https://learn.microsoft.com/en-us/windows/win32/procthread/job-objects) so child processes cannot keep the command's output pipe open after the runner exits. Background descendants are not durable services.

## Code intelligence

Tree-sitter parses **Python, JavaScript, TypeScript, Java, C#, C++, C, Go, Rust, and Ruby**, plus HTML and CSS. The index caches parsed files by content hash and refreshes changed/deleted files before queries. Common build/dependency directories and symlinks are excluded.

Tools include definitions, symbol search, callers, call trees, paths between functions, hierarchy, source outlines, name references, external/unresolved calls, symbol profiles, relevant-test selection, and forward/backward data-flow queries. They distinguish resolved bindings, ambiguous candidates, external imports, and unknown calls. Python import scopes and signatures have dedicated handling; explicit import bindings also cover common JavaScript/TypeScript, Go, Rust, Java, and C# forms.

Data-flow queries follow syntactic dependencies through arguments, assignments, returns, and subsequent calls. They preserve ambiguous call candidates and are not path-sensitive runtime proofs. Relevant tests are selected through resolved call paths and test naming conventions; tests reached only by dynamic dispatch can be missed.

HTML queries include static markup embedded in Python string literals. CSS analysis covers linked document scope, specificity, source order, `!important`, inline styles, common inherited properties, and basic custom-property substitution. DOM queries locate literal `querySelector`, `querySelectorAll`, and `getElementById` selectors. Unsupported dynamic selectors, conditional rules, and missing stylesheets are reported rather than silently applied. This is not a browser layout engine.

## Editing and verification

Source changes use atomic replacement and durable before/after snapshots. Syntax errors reject the edit before writing. A semantic gate rejects known call bindings that become unresolved and newly invalid statically known Python call signatures. It is not a complete type checker. Edit results include diffs and caller impact so the model can select and run relevant tests.

The `apply_edits` tool validates up to 100 files together, allowing coordinated changes such as updating a function signature and its callers. All required path approvals finish before the first write. Each file is replaced separately; this is not a filesystem-wide atomic transaction. A write failure attempts to restore the group's previous bytes while preserving conflicting external changes.

Undo restores the previous bytes, including original newlines. It refuses to overwrite subsequent user changes. Pending snapshots are recovered after restart by comparing their before/after content with the current file. Generated reproductions and runtime traces are stored under `.banger/`.

Grouped edits undo as one operation. Restart recovery classifies unfinished groups without rewriting source files: a partially applied group can be explicitly undone if its files still match the recorded before/after bytes. Groups with conflicting external changes are preserved for manual inspection.

Python runtime tracing runs the target in a separate interpreter and records calls, arguments, returns, exceptions, and parent-call relationships. Recorded dispatch augments symbol profiles only while the source hashes still match. Other languages can execute tests through their normal command-line tools, but do not have runtime tracing in this version.

## State and model adapters

`.banger/state.db` stores conversations, project facts, parsed indexes, snapshots, and recorded results. The full conversation remains on disk when older model-context results are shortened; history and saved tool-output tools can recover omitted content. Context reduction uses explicit excerpts, not an inferred semantic summary.

The provider adapters implement [Anthropic tool-use messages](https://platform.claude.com/docs/en/agents-and-tools/tool-use/handle-tool-calls) and [OpenAI-compatible Chat Completions messages](https://developers.openai.com/api/reference/cli/resources/chat). Streaming tool arguments are assembled before execution. Interrupted or truncated responses are not executed. Transient server and connection failures have bounded retries. There is no subscription-account login integration.

## Verification and current limits

```console
uv run pytest
uv run ruff check src tests
uv run ruff format --check src tests
```

The tests use our own source fixtures. They cover each code language's basic definitions/calls, selected cross-file imports, ambiguity, data flow, markup, syntax/semantic gates, undo and recovery, approvals, model protocols, real command execution, tracing, and headless terminal interactions. End-to-end tests edit a buggy function and execute a real reproduction through both mocked provider protocols.

A live OpenAI-compatible coding task and streaming tool-call checks passed against the user's local endpoint. GitHub Actions runs tests, lint, formatting, and package builds on Windows, Linux, and macOS with Python 3.11 and 3.13; see [CI results](https://github.com/skanga/banger/actions/workflows/tests.yml) for each commit's status. Live Anthropic access remains unverified. Benzi's private compiler is unavailable, so exact behavioral equivalence cannot be asserted. Complex type inference, overload selection, macros, dynamic imports/dispatch, exhaustive CSS semantics, and full language-specific semantic analysis remain areas for further work. See [the feature audit](docs/FEATURE_AUDIT.md) for the distinction between implemented behavior and remaining verification.
