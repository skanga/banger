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
- **Sessions:** select a saved conversation to resume it, including formatted assistant messages and saved tool results.
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

Edit approvals show the proposed full content or separate old/new replacement blocks with real line breaks. Grouped deletions are labeled explicitly. These are proposals supplied by the model, not computed comparisons with the current file; the Diffs tab shows the resulting edit diffs.

Native Windows execution uses cmd, and Linux/macOS execution uses bash. Bash can also be selected on Windows when a functioning bash installation is available on PATH. Commands run independently in the selected working directory; shell state does not persist between calls. Output is bounded, commands have timeouts, and cancellation terminates their process tree. Windows runners use [job objects](https://learn.microsoft.com/en-us/windows/win32/procthread/job-objects) so child processes cannot keep the command's output pipe open after the runner exits. Background descendants are not durable services.

## Code intelligence

Tree-sitter parses **Python, JavaScript, TypeScript, Java, C#, C++, C, Go, Rust, and Ruby**, plus HTML and CSS. The index caches parsed files by content hash and refreshes changed/deleted files before queries. Common build/dependency directories and symlinks are excluded.

In Git workspaces, code and markup discovery uses [Git's tracked and untracked file listing](https://git-scm.com/docs/git-ls-files) with standard ignore rules. Nested ignore files and exceptions apply to untracked files; tracked files remain eligible outside Banger's fixed exclusions. Index refresh notices changed ignore rules. Ignored stylesheets are reported as unavailable. Submodules and nested repositories are not expanded automatically. Direct file reads and source browsing still allow explicit inspection under the selected permission mode.

Git must be installed and able to read a Git workspace. Discovery errors, including ownership errors, are reported without bypassing Git's trust checks or falling back to scanning ignored files. Plain folders without a Git ancestor use the filesystem scan and fixed exclusions; standalone `.gitignore` files in those folders are not interpreted.

Native console interaction has been checked on Windows and in Linux/macOS PTYs. POSIX CI exercises setup, permission selection, mouse navigation and terminal cleanup at 80x24 and 120x40; emulator-specific rendering can still differ.

Chat and tool output wrap to the available pane width and reflow when the terminal resizes or a hidden tab becomes visible. Restored conversations use the same wrapping and Markdown rendering.

Tools include definitions, symbol search, callers, call trees, paths between functions, hierarchy, source outlines, name references, external/unresolved calls, symbol profiles, relevant-test selection, and forward/backward data-flow queries. They distinguish resolved bindings, ambiguous candidates, external imports, and unknown calls. Python import scopes and signatures have dedicated handling; explicit import bindings also cover common JavaScript/TypeScript, Go, Rust, Java, and C# forms.

Ruby hierarchy queries preserve complete superclass expressions and resolve preceding local class declarations through lexical module/class nesting and qualified or absolute constant paths. Reassigned constants, conditional/reopened classes, mixins and inherited-constant lookup remain unproven. Cross-file candidates retain uncertainty about Ruby file loading; metaprogramming and constant aliases are not evaluated.

C++ hierarchy queries preserve qualified base expressions and resolve preceding class definitions in the same file's namespace and class scopes. Cross-file include visibility, template expansion, aliases, and preprocessing remain unproven and are reported as candidates or unknowns. Local classes and shadowing namespaces are kept separate.

Data-flow queries follow syntactic dependencies through arguments, assignments, returns, and subsequent calls. They preserve ambiguous call candidates and are not path-sensitive runtime proofs. Relevant tests are selected through resolved call paths and test naming conventions; tests reached only by dynamic dispatch can be missed.

Module-level assignments can connect return holders to subsequent call arguments. Module values and expressions are keyed by source file, so matching names or expressions in unrelated files remain separate. Python flow follows explicit `from` imports, aliases, re-export chains and direct module-attribute reads through `import` bindings. Competing module locations retain ambiguous candidates. Indirectly imported module objects, dynamic imports and assignment order across branches remain unresolved.

Python expression dependencies use AST reads, excluding string text, attribute labels, keyword labels and names bound within lambdas or comprehensions. Reads in f-strings, lambda defaults and comprehension iterables remain visible. Other languages currently retain lexical expression approximations.

Forward/backward dependency graphs return at most 1,000 nodes and flag `truncated` when reachable nodes were omitted. Returned edges always refer to returned nodes. This is a graph-node limit, not a byte limit on the full tool response or an index-memory limit.

Python flow queries bind explicit arguments using indexed signatures, including positional-only, keyword-only and variadic parameters. Ordinary implicit-receiver calls retain their candidate resolution evidence. Omitted defaults include their declared expression, file, line and enclosing scope; this is source provenance, not the current value of a mutable default object. Dynamic splats and signatures hidden by decorators remain unresolved. Other languages currently use positional argument approximations.

HTML queries include static markup embedded in Python string literals. CSS analysis covers linked document scope, specificity, source order, `!important`, inline styles, common inherited properties, and basic custom-property substitution. Unsupported CSS selectors, conditional rules, and missing stylesheets produce unresolved evidence rather than being silently applied. This is not a browser layout engine.

Local unconditional CSS imports are expanded in order with imported-file provenance, cycle detection and depth/expansion limits. Disabled stylesheet links are not applied. Alternate stylesheets and media restrictions that require browser state remain unresolved.

DOM queries parse `querySelector`, `querySelectorAll`, and `getElementById` calls in JavaScript/JSX, TypeScript/TSX and inline JavaScript in HTML or extracted Python markup. Comments, string examples and HTML text are excluded. Constant string escapes, untagged constant templates and literal bracket method access are supported. Results are syntactic candidates, not proof of the receiver's runtime identity or execution. Dynamic selector expressions, tagged/interpolated templates, event-handler attributes and legacy numeric escapes are not resolved and can be absent from results.

Static selectors support descendant, child (`>`), adjacent-sibling (`+`) and subsequent-sibling (`~`) relationships between elements, including mixed chains. Sibling matching stays within a parent and document; text and comments do not interrupt element adjacency. These relationships follow [Selectors Level 4](https://www.w3.org/TR/selectors-4/#adjacent-sibling-combinators).

Attribute selectors support presence, equality, word (`~=`), hyphen-prefix (`|=`), prefix (`^=`), suffix (`$=`) and substring (`*=`) matching, plus explicit ASCII-insensitive `i` and sensitive `s` flags. Quoted punctuation remains part of the attribute value. CSS escapes and namespaces remain unsupported; unflagged values use a case-sensitive approximation rather than all HTML attribute-specific rules.

Style reports include the source file and rule-start line, preserving that origin through inheritance. Inline `style` attributes point to the containing element's start line. Python markup literals map decoded characters to source lines through escapes, line continuations and implicit adjacent-literal concatenation. Separate literals on the same line remain distinct documents. Element reports label exact literal maps and approximate fragments; dynamic f-strings and runtime string construction do not have exact maps.

Python f-strings are indexed as whole template skeletons. Unevaluated expressions appear in query warnings, including when no static element matches. Template elements are marked dynamic, and their style reports contain static candidates rather than final runtime styles; interpolation can change the document structure.

## Editing and verification

Source changes use atomic replacement and durable before/after snapshots. Syntax errors reject the edit before writing. A semantic gate rejects known call bindings that become unresolved and newly invalid statically known Python call signatures. It is not a complete type checker. Edit results include diffs and caller impact so the model can select and run relevant tests.

The gate distinguishes callers by their enclosing scopes. An unrelated same-name candidate cannot stand in for a removed target, and deleting an imported project module does not silently reclassify its unchanged import as an external dependency. Explicit import changes remain possible. Existing Python argument errors are counted per caller/call name so they do not mask additional bad calls.

The `apply_edits` tool validates up to 100 files together, allowing coordinated changes such as updating a function signature and its callers. All required path approvals finish before the first write. Each file is replaced separately; this is not a filesystem-wide atomic transaction. A write failure attempts to restore the group's previous bytes while preserving conflicting external changes.

Undo restores the previous bytes, including original newlines. It refuses to overwrite subsequent user changes. Pending snapshots are recovered after restart by comparing their before/after content with the current file. Generated reproductions and runtime traces are stored under `.banger/`.

Grouped edits undo as one operation. Restart recovery classifies unfinished groups without rewriting source files: a partially applied group can be explicitly undone if its files still match the recorded before/after bytes. Groups with conflicting external changes are preserved for manual inspection.

Python runtime tracing runs the target in a separate interpreter and records calls, arguments, returns, exceptions, and parent-call relationships. Recorded dispatch augments symbol profiles only while the source hashes still match. Other languages can execute tests through their normal command-line tools, but do not have runtime tracing in this version.

Argument records include positional-only, keyword-only and variadic groups. Synchronous generators, async generators and native coroutines keep invocation identities across suspension and resumption. Yields, await suspensions, successful returns and exceptional exits are distinguished; an internal exception event does not necessarily mean an exception escaped the function. Async-generator yielded values are extracted from CPython's internal wrapper through GC traversal and use the same safe-value limits. Lifecycle classification depends on CPython instruction and wrapper details; native CI covers Python 3.11 and 3.13.

Trace values are bounded: strings retain up to 500 characters, supported collections up to ten entries within two nesting levels, and integers above 1,024 bits become summaries with sign and bit length. Other objects retain type summaries without calling their `repr`. The program's own values are unchanged. Traces stop recording after 10,000 events and report truncation.

## State and model adapters

`.banger/state.db` stores conversations, project facts, parsed indexes, snapshots, and recorded results. The full conversation remains on disk when older model-context results are shortened; history and saved tool-output tools can recover omitted content. Context reduction uses explicit excerpts, not an inferred semantic summary.

The provider adapters implement [Anthropic tool-use messages](https://platform.claude.com/docs/en/agents-and-tools/tool-use/handle-tool-calls) and [OpenAI-compatible Chat Completions messages](https://developers.openai.com/api/reference/cli/resources/chat). Streaming tool arguments are assembled before execution. Interrupted or truncated responses are not executed. Response and tool-call structures are validated before saving the assistant message or running any tool in the batch. Valid calls execute sequentially; a later runtime failure does not roll back earlier calls. Transient server and connection failures have bounded retries. There is no subscription-account login integration.

Recovery pairs tool results with call occurrences, so a reused ID in a later response cannot hide an interrupted call. Duplicate IDs within one response, blank IDs and non-string IDs are rejected before tools run. Large outputs use independent artifact IDs to preserve earlier results when a model reuses a call ID.

## Verification and current limits

```console
uv run pytest
uv run ruff check src tests
uv run ruff format --check src tests
```

The tests use our own source fixtures. They cover each code language's basic definitions/calls, selected cross-file imports, ambiguity, data flow, markup, syntax/semantic gates, undo and recovery, approvals, model protocols, real command execution, tracing, and headless terminal interactions. End-to-end tests edit a buggy function and execute a real reproduction through both mocked provider protocols.

A live OpenAI-compatible coding task and streaming tool-call checks passed against the user's local endpoint. GitHub Actions runs tests, lint, formatting, and package builds on Windows, Linux, and macOS with Python 3.11 and 3.13; see [CI results](https://github.com/skanga/banger/actions/workflows/tests.yml) for each commit's status. Live Anthropic access remains unverified. Benzi's private compiler is unavailable, so exact behavioral equivalence cannot be asserted. Complex type inference, overload selection, macros, dynamic imports/dispatch, exhaustive CSS semantics, and full language-specific semantic analysis remain areas for further work. See [the feature audit](docs/FEATURE_AUDIT.md) for the distinction between implemented behavior and remaining verification.
