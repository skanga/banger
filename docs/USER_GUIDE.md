# Banger user guide

See the [README](../README.md) for pip and uv installation commands.

## Configure a model

Launch `banger` in the project directory or run `banger /path/to/project`. Use `banger --setup /path/to/project` to change an existing configuration.

| Setting | What to enter |
|---|---|
| Provider | Anthropic, or OpenAI-compatible / local. |
| Model ID | The exact model identifier accepted by your endpoint. |
| API base URL | The API prefix: `https://api.openai.com/v1`, `https://api.anthropic.com/v1`, or your local server's API URL. |
| API key | A provider key, or leave blank to use its environment variable. Local servers may not require a key. |
| Stronger model | An optional model on the same provider and endpoint. Switching requires confirmation. |
| Shell | `cmd` on Windows or `bash` on Linux/macOS. Windows can also use bash if it is installed and on PATH. |
| Permission mode | Read-only, ask, accept-edits, or full-access. |

The OpenAI-compatible option requires Chat Completions tool calling. Banger has no subscription-account login flow; select a model and endpoint that accept API requests.

### Supply an environment key

In PowerShell:

```powershell
$env:OPENAI_API_KEY = "your-api-key"
banger
```

In bash or zsh:

```sh
export OPENAI_API_KEY="your-api-key"
banger
```

For Anthropic, replace `OPENAI_API_KEY` with `ANTHROPIC_API_KEY`. These examples set the variable for the current shell and its child processes. Use your preferred environment configuration to make it available in future terminals. Banger does not read `.env` files itself.

Keys entered in setup remain in memory. Model settings and permission mode are saved per project, but the key is not saved in configuration. If a required key is missing on restart, setup opens with the previous settings selected.

## Work on a task

Give Banger the intended result and relevant file, symbol, or failing command. For example:

- “Explain the callers of `load_config` and identify tests that exercise them.”
- “Search `src` for references to the deprecated endpoint.”
- “Fix the failing parser test, update its callers if necessary, and rerun affected tests.”
- “Make a plan for this refactor and update it as you finish each step.”

Use Tools to inspect what actually ran and Diffs to inspect edits. Responses and tool output wrap to the pane width. Source is a read-only viewer; ask for changes in Chat or edit files in your own editor.

The file tree checks loaded directories approximately once per second for additions, removals, and renames. Expanded folders and selection are preserved where they still exist. Unopened directories load when expanded. Content-only changes do not rebuild the tree; reselect a file to read its current contents in Source.

The Working animation covers model requests and tool execution. Approval requests replace it with Action required. Escape interrupts a task, but an already-started command may have partial effects. Inspect its result and affected files before retrying.

## Approve actions

Read-only mode permits exploration but denies edits and commands. Ask mode prompts for edits and commands. Accept-edits permits project edits automatically while retaining command approval. Full-access permits edits and commands automatically, including built-in access outside the project.

An approval dialog shows the proposed action. Choose **Allow once**, **Deny**, or **Remember for session** where available. Escape denies the request. Remembered command approvals apply to the exact command and working directory; remembered read approvals apply to the exact path.

Ctrl+P changes the mode for subsequent actions and saves it for the project. It does not stop a running command; interrupt that separately. Ctrl+N starts a new conversation and clears remembered action approvals. The saved permission mode is separate from those temporary approvals.

Commands execute directly on the host. Each call starts independently in the selected working directory, so shell variables and directory changes do not persist between calls. Output and runtime are bounded. Interrupting execution terminates its process tree; background child processes are not durable services.

## Search and understand code

Banger parses Python, JavaScript, TypeScript, Java, C#, C++, C, Go, Rust, and Ruby, plus HTML and CSS. Ask for definitions, source outlines, callers, call trees, paths between functions, class relationships, references, symbol profiles, relevant tests, or forward/backward data flow.

Results distinguish resolved relationships from ambiguous candidates, external imports, and unknown calls. Python has the most detailed scope and argument analysis. Dynamic dispatch, macros, complex type inference, and some module relationships remain unresolved. Use the project's tests and compiler to verify proposed changes.

Literal and regex search works without shell execution, including in read-only mode. Specify a file or directory to narrow a search. Results include line numbers and match columns; binary, non-UTF-8, and oversized files can be skipped. Limits are 2 MiB per file, 32 MiB per query, and 10,000 discovered files. Regex searches have a 10-second deadline; narrow the scope or simplify the expression if one times out.

In Git projects, code discovery uses Git's tracked-file and untracked-file listings with ignore rules. Fixed exclusions such as `.git`, `.venv`, `node_modules`, build directories, and symlinks are omitted. Tracked files remain eligible despite ignore rules unless covered by a fixed exclusion. Plain folders use filesystem discovery and fixed exclusions; standalone `.gitignore` files are not interpreted there.

HTML/CSS queries inspect static elements, selectors, styles, and JavaScript DOM references, including markup embedded in Python strings. Dynamic markup and browser-dependent CSS can produce partial results. These queries do not run a browser or compute layout.

Ask Banger to list declared dependencies to inspect supported Python, JavaScript, Rust, Go, Maven, and .NET manifests. This reports declarations; it does not install packages or establish installed versions.

For detailed tool contracts, ask Banger to use built-in `read_reference` help with the `tools`, `languages`, or `artifact` topic.

## Edit, verify, and undo

Edit tools validate proposed source changes before writing. Syntax errors and certain regressions in known call bindings or Python argument signatures reject an edit. This does not replace a type checker, compiler, or test suite. Ask Banger to run relevant checks after changing code and inspect their output in Tools.

Approval details contain proposed full content or old/new replacement blocks. Diffs contains the resulting edit diffs. Coordinated edits can validate up to 100 files together, but files are written separately rather than as one filesystem-wide atomic transaction.

To undo, ask “Roll back the latest edit.” The `rollback_edit` tool restores previous bytes for the latest edit snapshot or group, subject to permissions and conflict checks. It refuses to overwrite conflicting changes you made afterward. Arbitrary shell changes are not covered by edit snapshots.

After interruption or restart, ask Banger to inspect the last execution and pending edit state before continuing. An unfinished edit group can be undone when its files still match recorded before/after contents; conflicts require inspection.

## Trace Python execution

Ask Banger to trace a Python reproduction or test to inspect calls, arguments, returns, exceptions, and parent calls. Tracing runs the target program and follows command permissions. Other languages can run through ordinary commands but do not have runtime tracing.

Traces preserve relationships across generator yields and coroutine suspension. Values are summarized and events are capped at 10,000; check incomplete or truncated markers. Recorded call relationships are used with source profiles only while the recorded source hashes match current files.

## Resume work and manage state

Each project keeps `.banger/state.db`: settings, conversations, project facts, plans, indexes, edit snapshots, and recorded results. Generated reproductions and traces also live under `.banger/`. Keep this directory out of version control and retain it for conversation history and undo data. Conversations and command output can contain project-sensitive information.

Open Sessions and select a conversation to resume its messages and tool results. Automatic startup restores configuration; select a prior conversation explicitly to continue it. Ctrl+N starts a separate conversation.

Plans belong to individual conversations and survive restarts. Project facts are shared across conversations in the same project. Ask Banger to remember a fact, list remembered facts, or forget one by its exact key. Forgetting a fact removes it from future project-memory context but does not erase earlier mentions in history.

Long outputs and older context may be shortened for the model. Original saved history and output remain available through recovery tools. Ask Banger to read saved history, retrieve a tool-output artifact, inspect the last execution, or recover the plan instead of repeating an action with uncertain side effects.

## Troubleshooting

| Symptom | What to check |
|---|---|
| `banger` is not found | For uv, run `uv tool update-shell` and reopen the terminal. For pip, activate its environment or run its Python with `-m banger`. |
| Setup opens on every launch | Use the same project directory, ensure `.banger` is writable, and provide any required environment key. Typed keys do not survive restart. |
| Authentication or connection error | Check the provider, exact model ID, API base URL, key, and whether a local server is running. |
| Local model cannot use tools | Check that the endpoint and model support Chat Completions tool calling. |
| First source query cannot load a grammar | Check network access for the grammar download and access to the language-pack cache. |
| Git discovery fails | Confirm Git is installed and works in the project. Resolve ownership or access problems in Git; Banger does not bypass its trust checks. |
| New files do not appear | Allow approximately one second, expand their parent folder, and check fixed exclusions. |
| No animated tab title or approval sound | Check whether the terminal permits title changes and has its bell enabled. |
| A change is rejected | Read the validation error, inspect affected callers, and include coordinated changes where necessary. |
| Undo reports a conflict | Inspect edits made since the snapshot; undo will not overwrite them automatically. |
