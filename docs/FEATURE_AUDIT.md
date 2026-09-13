# Banger feature and verification audit

This audit preserves the user's target: an independent terminal coding agent with the best attempt at Benzi-equivalent capabilities. The working application is not proof of exact compiler parity.

| Requirement | Current evidence | Remaining limits or verification |
|---|---|---|
| Python + uv application in the current directory | Isolated Windows wheel installation and live coding task; native CI tests/builds on all three platforms | Installed-wheel live task was Windows only |
| Independent implementation; mini-swe-agent optional | Banger source imports no Benzi/mini-swe-agent modules | No proprietary implementation available for differential comparison |
| Terminal UI; no graph | app.py, test_tui.py, test_end_to_end.py; regenerated 120x40 SVG rendered and visually inspected | Snapshot uses deterministic model responses; not a live terminal recording |
| Chat, source, diffs, tools, sessions, interrupt, mouse | Textual interaction tests, including 80x24 setup and approval controls | Native terminal emulators can differ from headless interaction tests |
| All ten code languages | test_index.py query matrix; test_language_edits.py tool-level gates, impact and restart undo | These tests do not invoke every language's compiler or prove complete language semantics |
| Cross-file bindings | test_cross_language.py; Python import tests | Advanced module systems, overloads, macros, dynamic dispatch remain partial |
| Definitions, callers, closure, paths, hierarchy, references, outlines | index.py, analysis.py, hierarchy.py, tools.py; query tests | Hierarchy resolves common Python, Java, C#, JS and TS bindings plus same-file C++ lexical bases; other forms retain candidates or unknowns. References retain syntactic scope rather than full type binding |
| Forward/backward flow across calls | test_flow.py, test_flow_arguments.py, test_flow_defaults.py, test_flow_scopes.py, test_flow_imports.py, test_flow_module_attributes.py; Python signatures, defaults, scopes, imported values and direct module attribute reads | Path-insensitive; ambiguous edges remain candidates; splats and decorated signatures unresolved; runtime values, indirectly imported module objects and dynamic imports unverified; other languages use positional approximations |
| Markup, CSS, DOM-JS, Python-embedded markup | test_markup.py | Conditional/browser-dependent rules, computed layout and exhaustive selector/cascade semantics not implemented |
| Syntax and semantic write gates | test_edits.py, test_batch_edits.py, test_language_edits.py; syntax and lost-binding rejection across all ten languages, combined validation for coordinated changes | Semantic gate covers known call regressions and Python signatures, not complete type checking |
| Impact and relevant tests | Matching before/after edit reports with callers, value consumers, and relevant tests; persisted by snapshot ID | Test selection can miss dynamically invoked tests; reports do not execute tests |
| Runtime tracing and static overlay | test_tracing.py; hash-validated runtime profile edges | Python only; traces are bounded and large/custom values are summarized |
| Generated reproductions and local execution | test_end_to_end.py, test_execution.py; native cmd and Linux/macOS bash checks passed in CI | Commands run on the host; no container isolation |
| Undo and restart recovery | test_edits.py, test_state.py, test_batch_edits.py, test_undo_recovery.py; single/grouped undo and incomplete-operation classification | Arbitrary shell changes are not captured by edit snapshots; multi-file writes are not filesystem-wide atomic |
| Persistent conversations, memory, index, trace, undo | StateStore, restart tests, context tests | Context excerpts are not a lossless in-context summary; exact history stays available on disk |
| Anthropic/OpenAI-compatible/local model interfaces | Mocked provider tests plus live OpenAI-compatible streaming/tool execution with gpt-5.3-codex-spark | Anthropic live endpoint unverified; local models must support tool calling |
| Escalation confirmation | test_agent.py, test_permissions.py | Stronger model is configured for the same provider/endpoint |
| Selectable familiar permission modes | Policy tests, TUI approval/mode-switch tests | Local execution has no filesystem/network sandbox |
| Windows/Linux/macOS with cmd/bash | Six native CI jobs passed on Python 3.11 and 3.13; shell, process, tracing and headless TUI tests included | Hosted runner images do not cover every terminal, OS release or architecture |
| Containers | Explicitly deferred by user | Later version |
| No headless agent/API/benchmark requirement | Only interactive application launcher | Internal Python modules exist for implementation/testing |

## Next verification gates

1. Full local Windows suite passed: 433 tests; ten-language edit acceptance, scoped semantic-gate regressions, compact-terminal interaction, grouped edits, single-file undo recovery, repeated tool-ID recovery, Python flow argument binding and default origins, module flow isolation, expression scopes, graph limits, call-query scaling, CSS sibling/attribute selectors and source provenance, embedded literal source maps, dynamic template uncertainty, shutdown recovery, C++ hierarchy and Git discovery are included. Native CI results are recorded separately below.
2. Wheel and source distribution built; isolated Windows installation passed launcher and live agent checks.
3. Native Windows, Linux and macOS CI passed on Python 3.11 and 3.13; see the recorded run below.
4. Live OpenAI-compatible coding task passed on 2026-09-11; see details below. Other providers remain covered by mocked tests.
5. Continue strengthening language and markup analysis where the current evidence is narrower than Benzi's described capability.

## Python global and closure value flow

The index persists compiler scope classifications from Python's standard-library
[symtable](https://docs.python.org/3/library/symtable.html), without executing
project code. Flow reads and assignment/return holders now share variable
identities for global and closure bindings. Method reads skip class-local values
when Python resolves the name to an enclosing function or module. Explicit
`global` and `nonlocal` writes reach consumers of the corresponding binding.
The file-cache version was advanced so existing indexes rebuild this metadata.

Eleven cases in `test_flow_scopes.py` cover forward/backward traversal, module
and closure reads, methods, local/import/loop shadowing, global/nonlocal writes,
outer-scope defaults and persisted-index restart. Six initial positive cases
failed before implementation; three shadowing cases already passed. Two further
cases verify globals created inside functions and outer-scope defaults.
The full local suite passed 360 tests, plus Ruff lint/format and package builds.
This does not resolve imported value origins, class-body execution order,
dynamic rebinding, or all modern annotation/type-parameter scopes. Dependency
graphs remain path-insensitive and do not prove runtime values.

Commit `02845d679551f21c496a30ba8146406d122b5dda` passed all six native
Windows/Linux/macOS and Python 3.11/3.13 jobs, including tests, lint, formatting
and package builds: [CI run 34723188126](https://github.com/skanga/banger/actions/runs/34723188126).

## Compatible-provider HTTP errors

OpenAI-compatible HTTP 400 responses retain their HTTP status and response body
even when a local endpoint or proxy returns empty/non-JSON content or an
unexpected JSON shape. Only an explicit unsupported `max_tokens` parameter
error triggers the existing `max_completion_tokens` fallback. Other 400 errors
are raised without an automatic retry or configuration mutation; a subsequent
request can succeed on the same client.

Nine cases in `test_models.py` verify those boundaries and follow-up recovery.
Seven cases failed before the fix with JSON parsing or attribute-access errors;
two further structured-error cases ensure unrelated errors do not switch the
token parameter. Existing successful fallback and provider round trips remain
covered. This improves request-error reporting, not automatic remediation of
invalid prompts or endpoint configurations.

Verification: all 433 local Windows tests passed, with Ruff lint/format checks
and wheel/source-distribution builds. Commit
`a5d3c15f9a18cf5bc63b4835b43d23b1cb48426b` passed all six native Windows,
Linux and macOS jobs on Python 3.11 and 3.13, including tests, lint, formatting
and builds: [CI run 34740202935](https://github.com/skanga/banger/actions/runs/34740202935).

## Command launch reservation

The executor reserves its command slot before awaiting subprocess creation and
releases it after execution, launch failure or cancellation. Previously two
overlapping calls could both pass the idle check while the first process was
still starting. A deterministic delayed-launch regression failed before the
fix and now verifies rejection of the second call before a second launch.
Two additional cases verify a successful next command after a failed or
cancelled launch. Existing timeout and process-termination tests remain covered.
The reservation applies to one executor in its event loop; it is not a
system-wide process lock or an execution sandbox.

Verification: all 424 local Windows tests passed, with Ruff lint/format checks
and wheel/source-distribution builds. Commit
`35de7edc6715fb26be6f65b74335694ff5bd6b40` passed all six native Windows,
Linux and macOS jobs on Python 3.11 and 3.13, including tests, lint, formatting
and builds: [CI run 34739993845](https://github.com/skanga/banger/actions/runs/34739993845).

## Physical source lines and edit diffs

`read_file` now enumerates physical file lines, retaining Unicode separators,
vertical tabs and form feeds inside line content. It keeps only the requested
range while counting total lines. Single and grouped edits share a diff builder
that splits only CR/LF boundaries and preserves the source line endings.

Nineteen cases in `test_source_reads.py` cover agreement between indexed
definition locations and file-read ranges for LF/CRLF sources, exact Unicode
content, empty files, missing/final newlines, ordinary CR-only file reads,
out-of-range reads, and single/grouped diffs with exact edit/undo bytes. Ten
read cases and four diff cases failed before their fixes; five basic read
boundary cases already passed. Previously Unicode separators inflated line
counts and caused an extra diff context-prefix space inside a displayed string.
This verifies source/diff data; terminal rendering of unusual Unicode control
characters can still vary, and CR-only index-location agreement is unverified.

Verification: all 421 local Windows tests passed, with Ruff lint/format checks
and wheel/source-distribution builds. Commit
`49f9168a6295dd57b1d0b42fb9658e015f58845f` passed all six native Windows,
Linux and macOS jobs on Python 3.11 and 3.13, including tests, lint, formatting
and builds: [CI run 34739770175](https://github.com/skanga/banger/actions/runs/34739770175).

## Direct Python module attribute reads

Direct `import settings`, aliased imports and dotted module imports now connect
attribute reads such as `settings.VALUE` to known assignments or imported-value
bindings in the corresponding project module. The index persists the module's
access name and declaration scope separately from from-imported values. AST
expression traversal records attribute reads while excluding strings and names
bound inside lambdas or comprehensions. The file cache version was advanced.

Fourteen cases in `test_flow_module_attributes.py` verify both flow directions,
aliases, dotted modules, parameter/assignment shadowing, lambda/comprehension
scopes, local imports, closures, default arguments, ambiguous root/src layouts
and persisted-index reload. Five initial cases failed before implementation;
four exclusion cases already passed, and five scope/default/layout cases were
added afterward. Multiple module candidates remain marked ambiguous with their
paths; edges include the read and import locations.

This remains syntactic dependency analysis. It does not prove current module
object identity after reassignment, track arbitrary attribute writes, resolve
module objects imported through `from package import module`, or evaluate
dynamic import/module attribute hooks. Exact runtime search paths and execution
order remain unverified.

Verification: all 402 local Windows tests passed, with Ruff lint/format checks
and wheel/source-distribution builds. Commit
`2fca19212fa72ce6da107a539a8eb366c58f7862` passed all six native Windows,
Linux and macOS jobs on Python 3.11 and 3.13, including tests, lint, formatting
and builds: [CI run 34736009610](https://github.com/skanga/banger/actions/runs/34736009610).

## Python imported value origins

The index separately records `from ... import ...` value bindings with alias,
declaration scope, module/member, path and line. Flow connects project module
values to those aliases, including relative imports, root and `src/` layouts,
function-local imports, package initializers, re-exports and default arguments.
Import edges preserve source locations and mark multiple module-layout
candidates as ambiguous. The cache version was advanced to rebuild old indexes.

Ten cases in `test_flow_imports.py` cover forward/backward traversal, local and
parameter shadowing, index restart, source refresh and finite cyclic re-export
traversal. Six initial cases failed before implementation; two shadowing cases
already passed, and two package/default/refresh/cycle cases were added. This is
source-level dependency evidence, not proof that circular imports execute
successfully or that imported mutable values retain their current identity.
Module-object attribute access, star imports, dynamic import hooks, exact
runtime search-path precedence and branch/assignment ordering remain unresolved.

Verification: all 388 local Windows tests passed, with Ruff lint/format checks
and wheel/source-distribution builds. Commit
`c90f24921fb9ed46bead9c54c8a32dfce825d411` passed all six native Windows,
Linux and macOS jobs on Python 3.11 and 3.13, including tests, lint, formatting
and builds: [CI run 34727158472](https://github.com/skanga/banger/actions/runs/34727158472).

## Live installed-wheel CSS task, 2026-09-12

The wheel built from application commit
`036eca9515f3d8bb090d98fc9110e00095193d54` was installed into the existing
isolated Windows package-check environment. The harness asserted that Banger
loaded from `site-packages`. Wheel SHA-256:
`a1477feadfe9f103975735a8c48323606dee63b85f4ecc59337866e63e999465`.

Using streaming OpenAI-compatible `gpt-5.3-codex-spark` at the user's local
`http://127.0.0.1:10531/v1` endpoint without a key, the agent inspected an HTML
notice and its imported CSS. It changed the original color declaration in
`palette.css` from red to green, retained padding 4px and background white,
and verified those values with markup tools. The harness separately checked
the resulting style values and provenance, and that `page.html` and `site.css`
were unchanged. No overriding rule was added.

After closing and reopening SQLite, the harness verified exact conversation
recovery. A second live model request correctly summarized the changed file
and verified color from the saved session. Persisted rollback then restored
the original palette with one undo operation.

The edit task used accept-edits mode; the live follow-up used read-only mode.
No shell tool or stronger model was used. The model initially supplied an
incorrect element ID and copied a displayed line-number prefix into an edit;
the element lookup and syntax gate rejected those calls. It recovered and
finished successfully. This is one completed live coding task, not evidence
of error-free autonomous behavior or a live TUI interaction. Anthropic remains
covered by mocked provider tests.

Local evidence: `.banger/live-css-b48f4aaf/result.json`, its `.banger/state.db`,
and `.banger/live_css_acceptance.py`. The fixture's palette is restored to its
original red value after the undo check; the verified green styles and edited
content remain recorded in the result JSON. The same application commit had
already passed 378 local tests and all six native CI jobs recorded below.

## Local CSS imports

Markup analysis expands unconditional relative local `@import` rules in source
order, including quoted and `url(...)` forms, `all`, percent-encoded paths,
query/fragment suffixes, nested imports and Python-embedded styles. Imported
declarations preserve their CSS file and line. Refresh reloads changed imports.
Repeated imports retain their cascade position; ancestor cycles are reported.
This follows the applicable [CSS import rules](https://www.w3.org/TR/css-cascade-5/#at-import).

Fifteen cases in `test_markup_imports.py` cover cascade precedence, nested path
resolution, source provenance, refresh, cycles, unsupported/unavailable imports,
embedded styles and depth limits. Five initial cases failed before the change;
six negative cases already passed, and four further URL/provenance/limit cases
were added. Imports read only discovered workspace files. Remote URLs, unknown
root-relative URLs, CSS-escaped URLs, conditional or layered imports and imports
after ordinary rules remain explicit unresolved results. Expansion stops at
32 active stylesheet levels or 1,000 imported sheets per document; limits are
reported rather than silently treated as complete style analysis.

Verification: all 378 local Windows tests passed, with Ruff lint/format checks
and wheel/source-distribution builds. Commit
`036eca9515f3d8bb090d98fc9110e00095193d54` passed all six native Windows,
Linux and macOS jobs on Python 3.11 and 3.13, including tests, lint, formatting
and builds: [CI run 34724916650](https://github.com/skanga/banger/actions/runs/34724916650).

## Retrieval after context compaction

Compaction preserves the latest assistant tool-call batch and all its results,
so newly requested data reaches the next model invocation intact. Older tool
excerpts retain a saved artifact ID when present and point to `read_tool_output`;
ordinary excerpts continue to point to their exact `read_history` index.
Two cases failed before the fix; a further case covers multiple results in the
latest batch. The restart acceptance test uses the real read-only toolbox to
retrieve the missing tail from the saved artifact and checks that durable
history remains unchanged. The serialized budget still applies: an indivisible
latest batch larger than that budget is rejected rather than silently shortened.

Verification: all 363 local Windows tests passed, with Ruff lint/format checks
and wheel/source-distribution builds. Commit
`286e0013c6a1f310962fa007177b5486a7e3a3c2` passed all six native Windows,
Linux and macOS jobs on Python 3.11 and 3.13, including tests, lint, formatting
and builds: [CI run 34724298506](https://github.com/skanga/banger/actions/runs/34724298506).

## Serialized context limits

Context compaction now retains a latest message or complete tool-call/result
group that exceeds the preferred suffix size but fits the total serialized
budget with its history-retrieval notice. Excerpts are shortened against their
JSON-escaped size, so non-ASCII text cannot make the result exceed that budget.
Two new regression cases failed before the fix; additional cases cover a large
tool group and rejection of a genuinely oversized latest request. The six
context tests verify unchanged saved history, repeatable compaction and intact
call/result pairs. The limit remains a character budget for conversation JSON,
not a provider-specific token budget including system text and tool schemas.

Verification: all 349 local Windows tests passed, with Ruff lint/format checks
and wheel/source-distribution builds. Commit
`af65fd6d6ae2eaa4ac5684dd640b7ecd59d90e15` passed all six native Windows,
Linux and macOS jobs on Python 3.11 and 3.13, including tests, lint, formatting
and builds: [CI run 34721175268](https://github.com/skanga/banger/actions/runs/34721175268).

## Provider event framing

The Anthropic and OpenAI-compatible adapters assemble multiline SSE data fields
at blank-line event boundaries. A leading UTF-8 BOM is handled, comments and
unneeded metadata fields are ignored, and unfinished events at EOF are discarded.
Only CR, LF and CRLF delimit lines; Unicode separator characters inside model
text are preserved. This follows the relevant
[SSE framing rules](https://html.spec.whatwg.org/multipage/server-sent-events.html#event-stream-interpretation).

Eight new provider regression cases failed before implementation. They cover
both formats, all three line endings, fragmented UTF-8 network bytes, multiline
JSON, text callbacks and incomplete completion events. Additional Unicode-content
assertions exposed and fixed HTTPX's broader line-splitting behavior. Existing
tool-call round trips remain covered. This is payload framing for model requests,
not a browser EventSource implementation with event-ID reconnection.

Verification: 345 local Windows tests passed, with Ruff lint/format checks and
wheel/source-distribution builds. Commit
`451ea34ecef505879feb149b6dd9de3ac03e5fe3` passed all six native Windows,
Linux and macOS jobs on Python 3.11 and 3.13, including tests, lint, formatting
and builds: [CI run 34715301254](https://github.com/skanga/banger/actions/runs/34715301254).

## Model response validation

`tests/test_agent_recovery.py` covers malformed response roles/content, call lists,
function structures/names, argument types/JSON and duplicate or invalid IDs.
A malformed later call rejects the response before an earlier write executes or
the assistant message is persisted; a subsequent request can proceed. Explicit
null tool-call lists finish and resume as ordinary assistant messages. Eleven
new regression cases failed before the fix; two JSON-boundary cases were added
afterward. This validates response structures, not transactionality across valid
calls: later tool execution or approval failures can follow earlier effects.

Verification: all 335 local Windows tests passed, with Ruff lint/format checks
and wheel/source-distribution builds. Commit
`acb16d7915c71edc06fd6cafbb702eea9857b865` passed all six native Windows,
Linux and macOS jobs on Python 3.11 and 3.13, including tests, lint, formatting
and package builds: [CI run 34713827891](https://github.com/skanga/banger/actions/runs/34713827891).

## Live installed-package check, 2026-09-11

Used `gpt-5.3-codex-spark` at `http://127.0.0.1:10531/v1`, without an API key,
through the streaming OpenAI-compatible adapter. Banger was imported from the
isolated wheel installation, with tree-sitter-language-pack 1.18.0.

The agent fixed a deliberate subtraction bug in a disposable calculator fixture,
ran its unchanged addition assertions successfully, and executed a generated
reproduction with persisted runtime trace events. The harness independently reran
the assertions, checked that imports came from site-packages, and verified that a
resumed agent recovered the same conversation. The Windows command runner and
packaged trace runner both executed successfully.

The model initially searched outside the fixture, supplied some invalid symbol
identifiers, and made command quoting and timeout mistakes before recovering.
This demonstrates a completed basic live task, not reliable autonomous behavior
across arbitrary tasks. No stronger model was used. Full-access mode was used for
this disposable test; it does not constrain a process to the fixture directory.

Local evidence: `.banger/live-e3fc3228/result.json` and its `.banger/state.db`.

Follow-up regression: the live trace exposed synthetic interpreter filenames being
classified as project paths. The tracer now excludes angle-bracket interpreter
and generated-code labels. A failing-before/passing-after test verifies that only
the fixture source appears in project events; existing argument, return,
exception, and runtime-overlay tests remain green. The original live check used
the earlier wheel; this follow-up fix is covered by the local test suite.

Import-resolution follow-up: Python imports now consider root and `src/` layouts,
retain both candidates when search-path precedence is unknown, and exclude nested
methods from module-level imported functions. Missing members of indexed project
packages remain unknown, including during prospective edit checks. JavaScript and
TypeScript bare imports remain unknown because a package name may instead be a
project alias. Four regression tests failed before these changes and now pass.
Custom Python import paths, package re-exports, and JavaScript path-alias
configuration still need deeper resolution.

Declaration-card follow-up: definitions and profiles now include Python
docstrings and adjacent leading comments for the other nine code languages.
Twelve tests cover every language, decorated async methods, class documentation,
restart persistence, and rejection of detached or preceding-code trailing
comments. Non-Python comment formatting is preserved as source text rather than
interpreted as a documentation markup language. Cache version 8 reparses older
indexes to populate these fields.

Hierarchy follow-up: Python base expressions retain their qualification and
resolve against enclosing declarations and module imports, including aliases and
`src/` layouts. `subclasses` now contains only resolved relationships;
`candidate_subclasses` preserves uncertain matches. Five regression tests cover
duplicate names, imports, dotted bases, dynamic bases, enclosing scopes, refresh,
and value/parameter shadowing. Cache version 9 reparses older base expressions.
Other languages still expose candidate ancestry; Python metaclasses, dynamic
bases, and complete method-resolution ordering are not statically resolved.

Further hierarchy coverage: Java/C#/JS/TS base expressions now retain qualified
names and include implemented interfaces. Java package imports, C# namespace
imports, JavaScript default imports, TypeScript namespace imports, and local
class declarations resolve to indexed classes. C# declarations retain their own
namespace when a file contains several namespaces. Eight added tests cover these
cases and conflicting imported namespaces. Cache version 10 adds these parsed
fields. Generic base specialization, C# namespace-scoped using precedence,
Java wildcard imports, re-exports, and runtime class construction remain partial
or unresolved; this is not full compiler type checking.

TUI lifecycle follow-up: interruption clears unfinished streaming text; starting
or resuming a session clears prior session logs, and resume reconstructs tool
results and diffs from persisted messages. Four additional headless interaction
cases cover interruption, new-session isolation, and keyboard/mouse session
restoration through visible tabs. These verify interaction behavior, not visual
appearance in every terminal. A read-only `wsl.exe --list --quiet` probe found no
installed distributions, so native Linux execution remains unavailable here.

Scale follow-up: a 300-class/601-symbol fixture exposed a native access violation
with tree-sitter 0.26.0. An isolated comparison using the same language-pack
1.18.0 environment passed with tree-sitter 0.25.2 and failed again when 0.26.0
was restored. Banger now constrains the existing transitive parser dependency to
`>=0.25.2,<0.26` in its distributable requirements. The main environment uses
language-pack 1.17.0 and passes the new bounded subprocess regression plus the
full suite. This is an observed compatibility result, not a diagnosed upstream
memory-management cause.

Hierarchy edges and reverse relationships are now computed during refresh.
On the same Windows synthetic fixture, 20 profile queries took 0.295 seconds
before and 0.00027 seconds after this change; refresh took 0.032 and 0.048 seconds,
respectively. The benchmark asserts all 300 subclasses are returned. Local
reproducer: `.banger/bench_queries.py`; native-crash regression:
`tests/test_index_scale.py`. These timings do not establish performance on
arbitrary real-world repositories.

The rebuilt wheel was reinstalled in the isolated environment. Its requirements
automatically replaced tree-sitter 0.26.0 with 0.25.2, and the installed package
passed the same 601-symbol benchmark (0.048 seconds refresh; 0.00031 seconds for
20 queries).

Edit-impact follow-up: edits now return matching `impact_before` and
`impact_after` reports containing each file declaration, its callers, direct
return-value consumers, and tests reachable through resolved reverse call paths.
Reports persist in the `edit-impact` artifact keyed by snapshot ID. Tests verify
line changes across the edit, indirect test selection, exclusion of unrelated
tests, restart persistence, and explicit empty sides for creation/deletion.
A further regression ensures module-level return-holder references stay within
the caller's file. These are conservative static reports, not a claim that tests
have executed or that all dynamic effects are known.

Call-path follow-up: the model-facing `trace_path` tool now returns a structured
result with `found`, symbol IDs, and one step per edge of a shortest resolved
chain. Each step retains all matching call sites, source locations, argument
expressions, target parameter names, return holders, and resolution evidence.
Three regression tests cover multiple sites, keyword expressions, cycles,
unreachable targets, self-paths, and excluded ambiguous dispatch. The original
internal ID-list query remains available. Source expressions are not runtime
values, and parameter order alone is not claimed to bind keywords or splats.

Source-outline follow-up: `skim_source` now reads cached immediate body nodes
from the parsed tree instead of scanning line prefixes. It includes assignments,
returns and compound-statement headers with source ranges, without expanding
nested bodies. Eleven tests cover all ten languages, nested declarations,
100-entry output bounds, explicit truncation, and restart persistence. Outlines
are stored separately from declaration cards to keep symbol-search results
compact. Index cache version 11 refreshes older projects with the new data.

Execution-history follow-up: authorized attempts are recorded before execution,
with command, working directory, ID, and timestamps. Completion, timeout,
interruption and launch failures update that record instead of leaving an older
success visible. A new trace attempt clears the previous trace result. An
unfinished record read after restart is reported as an unknown outcome rather
than proof of a live process. Five tests cover cancellation, launch failure,
trace invalidation, restart, and a real completed shell command. Interrupted
processes may have partial side effects; the history does not imply rollback.

Approval-lifecycle follow-up: cancelling an approval now removes any mode-picker
overlay and the expired approval itself. A failing-before/passing-after TUI test
verifies that the old request cannot reappear when the overlay closes. Existing
approval and session interaction tests remain green.

A read-only self-index check of `src/banger` parsed 21 files and 218 symbols with
no syntax errors. Calls classified as 78 resolved, 308 ambiguous, 773 unknown,
and 282 external. This narrow-root check does not establish binding accuracy or
full semantics; many receiver calls remain unresolved. Native Linux/macOS
verification awaits an available repository/runner; the user has been asked for
that information.

Receiver-analysis follow-up: ordinary Python instance-method parameters are
identified during parsing. Calls through that implicit receiver retain methods
from the enclosing class's indexed descendants and their ancestors, excluding
unrelated same-name methods. These remain ambiguous candidates because dynamic
attributes, rebinding and runtime dispatch are not statically proven. Static or
decorated methods and explicitly reassigned receivers retain the broader
unknown-object behavior. Four tests cover overrides, inherited methods, static
parameters, and receiver reassignment. Cache version 12 adds receiver metadata;
hierarchy data is prepared before call resolution and prospective edit checks.

CSS follow-up: custom-property values resolve before inheritance, cyclic
definitions are invalidated, and ordinary declarations can use a fallback for an
invalid variable. Ordinary property names are normalized while custom-property
case is preserved. Attribute selectors validate their supported syntax and
distinguish an empty value from a presence check. Four regression cases failed
before these changes and now pass. Variable behavior was checked against the
[W3C custom-property specification](https://www.w3.org/TR/css-variables-1/).
Substitution remains bounded and supports a static subset; quoted variable
expressions and unsupported syntax are reported as unresolved. Full browser CSS
semantics and computed layout remain outside the implemented analyzer.

Grouped-edit follow-up: `apply_edits` validates the combined final state of up to
100 files before writing, so coordinated signature/caller changes can pass the
semantic gate together. Per-path approvals finish before writes, including undo.
Durable grouped snapshots support compensation after a write failure and grouped
undo after restart. Startup classifies incomplete operations without rewriting
source; conflicting external bytes are preserved. Tests cover syntax and semantic
rejection, denied apply/undo approval, create/delete with binary restoration,
injected apply/undo failures, partial recovery with and without external changes,
and migration of the prior snapshot schema. Multi-file visibility is not atomic;
compensation can itself fail, leaving an incomplete group for inspection.

A subsequent live adapter check with the same no-key local endpoint passed
streamed tool calls, argument decoding, tool-result follow-up, and streamed text.
This exercised the current source adapter; it did not rerun the entire coding task.

## Native CI, 2026-09-12 UTC

The user authorized creating `skanga/banger` for native CI. The private repository
contains the Banger implementation, tests, documentation, and locked dependencies;
the reference checkouts and local state are excluded.

The [initial six-job run](https://github.com/skanga/banger/actions/runs/34663734524)
passed all tests and package checks on Linux and macOS, using Python 3.11 and 3.13.
Both Windows jobs exposed the same shutdown race: a queued agent message tried
to update a widget after Textual removed it. A deterministic local regression
reproduced the failure. Agent events and worker cleanup now skip UI updates once
the app stops running. A second test verifies that closing during a model request
cancels the worker, closes HTTP resources, and preserves the saved conversation.
The [corrected run](https://github.com/skanga/banger/actions/runs/34664040928),
at commit `ffb456ec5f040032d63f9232ede5a35705d1105e`, passed all six jobs:

| OS | Python | Tests | Lint, formatting, wheel and source build |
|---|---|---|---|
| Windows | 3.11 | 160 passed | Passed |
| Windows | 3.13 | 160 passed | Passed |
| Linux | 3.11 | 160 passed | Passed |
| Linux | 3.13 | 160 passed | Passed |
| macOS | 3.11 | 160 passed | Passed |
| macOS | 3.13 | 160 passed | Passed |

These are native hosted-runner checks, including real cmd/bash execution and
Python tracing. TUI tests remain headless, and provider requests in CI are mocked.

## C++ hierarchy follow-up

Parsed C++ base expressions now retain namespace qualification and template
arguments while excluding access modifiers. Hierarchy links select preceding
complete definitions from the nearest same-file namespace/class scope. Function
and block-local classes do not leak into other scopes. Qualified lookup stops at
a shadowing namespace; unexpanded aliases and using declarations remain unknown.
Cross-file candidates do not establish include visibility. Conditional, template,
incomplete, and later declarations are not reported as resolved ancestry.

Fifteen regression cases cover these behaviors and cached restart/refresh.
The primary base-expression, lookup, alias-shadowing and local-scope cases failed
before implementation. Index cache version 13 rebuilds existing projects with the
new scope metadata. This remains a static subset of C++ lookup, without build
configuration, preprocessing, include expansion or template instantiation.

At commit `82cd2b774e9aba474504d65883a8e2f78babdcac`, the
[native C++ follow-up run](https://github.com/skanga/banger/actions/runs/34664666044)
passed 175 tests in each of the six Windows/Linux/macOS and Python 3.11/3.13 jobs.
Lint, formatting, and wheel/source builds passed in every job as well.

## Repository discovery follow-up

Code and markup indexes share Git-aware discovery. The implementation uses
`git ls-files -z --cached --others --exclude-standard`, preserving tracked source
while honoring standard ignore rules for untracked files. Refresh drops newly
ignored cached files and finds newly created source. Linked stylesheets must also
belong to the discovered file set. Fixed dependency/state exclusions remain in
effect. Submodules and nested repositories are not traversed automatically.

Nine tests cover nested ignores, negation, tracked ignored files, Unicode/space
filenames, ancestor rules, cache refresh, ignored markup/CSS/DOM references,
non-Git folders, unavailable Git, inherited Git environment variables, filesystem
monitor disabling, path boundaries, and ownership rejection. The five primary
behavior tests failed before implementation. Git discovery has a timeout,
disables filesystem-monitor hooks and optional locks, and does not override
repository trust. Plain folders retain the fixed-exclusion filesystem scan.

A read-only self-index check found 50 source files and 407 symbols with no syntax
errors, and no files from the ignored reference checkouts. The check initially
exposed mixed sandbox/user ownership of the Git metadata created during setup;
the `.git` directory owner was corrected to the normal user without changing
access rules or adding a global trust override.

The [native discovery run](https://github.com/skanga/banger/actions/runs/34665685211)
at commit `ed83b07afeb4687ffaf55ddcc4944e417724aa8a` passed 184 tests in every
Windows/Linux/macOS and Python 3.11/3.13 job, plus lint, formatting and both builds.

## Broader edit and TUI acceptance

Ten new tool-level acceptance cases exercise each requested code language through
`profile`, `write_file`, `replace_text` and `rollback_edit`. Each verifies syntax
rejection and lost-call-binding rejection without changing source or creating an
undo snapshot, a permitted arithmetic edit with before/after caller impact,
preserved CRLF bytes, four explicit edit approvals, and exact-byte undo after
reopening state. These are gate/persistence tests, not compiler or runtime checks
for the ten languages. All passed against the existing implementation.

A compact 80x24 interaction test verifies that the setup screen can scroll to its
Start button and a long approval proposal can be denied. The test disables scroll
animation before clicking to avoid racing the animation. The current 120x40
approval-and-edit test also regenerated `docs/tui-preview.svg`; it was rendered
with an isolated headless Chrome profile and visually inspected. Source tree,
tabs, chat, prompt, status and shortcuts were visible without overlapping
controls. The mock final response now accurately describes creating `hello.py`.
This is evidence for that rendered layout, not every terminal emulator or screen.

The first expanded CI run passed five jobs but exposed two timing-sensitive
Windows/Python 3.11 UI assertions. The compact approval test now waits for the
button's actual hit target and always cleans up its pending request. The session
test now clicks tabs and waits for the selected pane to render: direct reactive
tab assignments could be overwritten by queued focus messages. These changes
strengthen the test's user-flow evidence without changing application behavior.

The [corrected acceptance run](https://github.com/skanga/banger/actions/runs/34678392764)
at commit `d2d23b446b9597f176e3c13a42625c6c4a0c1089` passed 195 tests in every
Windows/Linux/macOS and Python 3.11/3.13 job. Lint, formatting, wheel and source
distribution builds passed in all six jobs.

## Semantic-gate regression follow-up

Gate comparisons now identify callers by path and enclosing declaration scopes,
and compare former targets with the candidates that survive the edit. Removing a
resolved target is rejected even when an unrelated same-name candidate remains.
Deleting an imported project module is also rejected when the unchanged import
would otherwise be reclassified as external. Explicit switches to a different
external import remain allowed; their runtime availability is not statically
verified. Added ambiguity is not itself treated as proof of a break when the
original declaration remains among the candidates.

Python argument errors use scoped counts rather than one flag per short caller
name. This prevents an existing error from suppressing additional bad calls or
errors in a different same-named nested function. Seven tests cover target loss,
module deletion, nested scopes, error counts, overload addition and explicit
external-import replacement; five regression cases failed before their fixes.
These comparisons are structural, not compiler proofs or complete source-diff
matching. Changes that rename callers or exchange existing errors between call
sites can still require runtime verification.

The first native run passed the semantic cases but exposed an approval-click race
in the older Windows/Python 3.11 end-to-end test. Both approval flows now share a
bounded helper that waits for the button's center to be visibly clickable. The
end-to-end test then waits for its actual worker to finish instead of polling a
running flag for a fixed number of iterations. This is test synchronization, not
a change to approval policy or application behavior.

The [final semantic-gate run](https://github.com/skanga/banger/actions/runs/34679546098)
at commit `749835d7e698c1a315e2a7c8875620b86bc815bd` passed 202 tests in every
Windows/Linux/macOS and Python 3.11/3.13 job. Lint, formatting, wheel and source
builds passed in all six jobs.

## Single-file undo recovery

Single-file undo now commits a pending-rollback marker before restoring bytes.
Restart recovery classifies a completed restoration as rolled-back, an untouched
edit as applied and retryable, and unrelated bytes as a conflict. Recovery does
not rewrite source files. Ordinary write exceptions use the same classification.
This prevents a completed but interrupted undo from blocking older undo history.

Nine cases cover interrupted undo of edits, creations and deletions, startup
classification, write failures before/after restoration, conflict preservation,
and retry. Six cases failed before the fix. The local full suite passed 211 tests;
Ruff lint and formatting checks passed. Interruption is injected at the write
boundary; these tests do not simulate power loss or provide filesystem-level
compare-and-swap protection against concurrent writers.

The [native undo-recovery run](https://github.com/skanga/banger/actions/runs/34680117126)
at commit `71bacfeb04c46a5be59bb0976fda10c8728a66cc` passed all six
Windows/Linux/macOS and Python 3.11/3.13 jobs, including tests, lint, formatting,
and package builds. Local wheel and source distribution builds also passed.

## Repeated tool-call IDs and recovery

Pending-call repair now processes conversation occurrences in order rather than
using a global set of answered IDs. A completed older call cannot suppress repair
of a later interrupted call with the same ID. Duplicate IDs within a response,
blank IDs and non-string IDs are rejected before saving that response or invoking
any tools. Large outputs now use independent artifact IDs instead of raw model
call IDs, preventing new results from overwriting older saved outputs.

Six cases cover resumed pending calls, malformed/duplicate IDs, safe follow-up
after rejection, large-output retention and actual asynchronous cancellation.
Five cases failed before the fix. All 322 local tests passed afterward, with lint
and formatting clear. Recovery reports uncertain action outcomes without retrying
the action. Previously overwritten artifact contents cannot be reconstructed by
this change; already malformed historical batches are not migrated.

The [native repeated-ID recovery run](https://github.com/skanga/banger/actions/runs/34713023865)
at commit `d799b6d341e2ba808ac5a33523955f7ff8f4bd08` passed all six
Windows/Linux/macOS and Python 3.11/3.13 jobs, including tests, lint, formatting
and package builds. Local wheel and source distribution builds also passed.

## CSS attribute operators and flags

Attribute selectors now support `~=`, `|=`, `^=`, `$=` and `*=` alongside presence
and equality. Explicit `i` uses ASCII-only case folding; `s` uses exact comparison.
HTML attribute names are matched without ASCII case distinctions. Quoted values
may contain selector punctuation and closing brackets, and specificity counts the
attribute selector rather than punctuation inside its value. Empty substring/word
operands do not match; word matching uses CSS whitespace. These semantics follow
[Selectors Level 4 attribute selectors](https://www.w3.org/TR/selectors-4/#attribute-selectors).

Twenty-four new cases cover operator results, explicit flags, non-ASCII case
distinctions, quoted punctuation, empty values, cascade specificity, invalid flags
and CSS whitespace. Seventeen new cases failed before implementation; the existing
prefix-selector rejection test was changed to require the newly supported match.
All 316 local tests passed, with lint and formatting clear. Escapes, namespaces
and unflagged HTML attribute-specific case rules remain outside this subset;
unflagged values retain the prior case-sensitive approximation.

The [native attribute-selector run](https://github.com/skanga/banger/actions/runs/34712409898)
at commit `b2c2fc1794713c990a08ebdbe363ca76c835beb1` passed all six
Windows/Linux/macOS and Python 3.11/3.13 jobs, including tests, lint, formatting
and package builds. Local wheel and source distribution builds also passed.

## Dynamic Python markup templates

F-strings are now extracted as whole template skeletons rather than walking their
literal fragments as separate documents. Unevaluated interpolations retain their
source expressions, including nested format values. Elements are marked dynamic;
query results expose unresolved templates even when the selector matches no static
element. Style reports preserve static candidates but state that interpolation may
change text, attributes, styles or element structure. Dynamic tag templates remain
visible as unresolved even when their skeleton yields no element.

Six cases cover structure around interpolations, static style candidates,
non-execution of interpolation calls, unmatched dynamic attributes, plain-literal
evidence, dynamic tags and nested format expressions. Two initial cases exposed
lost document structure, two established the uncertainty contract, and one added
case exposed dropped dynamic tags. All 292 local tests passed, with lint and
formatting clear. No project code is executed. Runtime structure and exact
f-string source maps remain unverified; these are explicitly partial templates.

The [native dynamic-template run](https://github.com/skanga/banger/actions/runs/34711991120)
at commit `aed03ce4dfff606d2f6349a22304d43f7ddab48d` passed all six
Windows/Linux/macOS and Python 3.11/3.13 jobs, including tests, lint, formatting
and package builds. Local wheel and source distribution builds also passed.

## Embedded Python literal source maps

Python markup literals now map each decoded character to its physical source line.
The mapper handles ordinary/raw literals, escape sequences, line continuations and
implicit adjacent-literal concatenation. It verifies that the decoded text matches
the AST value before returning an exact map. HTML elements and inline stylesheet
rules use that map, including CSS byte offsets after Unicode text. Literal IDs
include the source column so two literals on one line no longer overwrite a
document. Unsupported mappings retain an approximate-fragment label.

Ten cases cover escaped newlines/tags, adjacent literals, uneven indentation and
comments, continuations, Unicode text, raw literals, octal/named escapes and
same-line document isolation. Five initial cases reproduced incorrect locations or
document loss; two established the map-evidence contract. An additional uneven
indentation case failed before restoring grouping context during tokenization.
The complete local suite passed 286 tests. After an import-spacing correction,
all 37 markup tests passed again, with lint and formatting clear. The mapping
does not execute project code. Dynamic f-strings, explicit runtime concatenation
and generated markup remain outside exact literal mapping.

The [native embedded-literal run](https://github.com/skanga/banger/actions/runs/34710824423)
at commit `9bb1e6787e1867376854eac26547cbbbf9b9ba57` passed all six
Windows/Linux/macOS and Python 3.11/3.13 jobs, including tests, lint, formatting
and package builds. Local wheel and source distribution builds also passed.

## Markup source provenance

The document's source-line offset no longer overwrites HTMLParser's internal
column offset. Inline stylesheet rule locations start at the style content,
including multiline opening tags, instead of at the closing tag. Linked CSS
locations start at line one of the CSS file rather than inheriting the HTML link
line. Winning and inherited style reports now retain source path and rule-start
line; unsupported selector reports also carry those locations. Inline style
attributes point to the containing element's start line.

Seven cases cover inline/linked rules, multiline tags, inheritance, unsupported
selectors, embedded multiline Python markup and HTML element columns. Six initial
cases failed before the correction. All 276 local tests passed afterward, along
with lint and formatting. Escaped or concatenated Python string contents still
need an exact source map; these tests cover literal multiline source offsets.

The [native markup-provenance run](https://github.com/skanga/banger/actions/runs/34708678702)
at commit `8d6343c9a4146190d97659015304c9bd99cc7451` passed all six
Windows/Linux/macOS and Python 3.11/3.13 jobs, including tests, lint, formatting
and package builds. Local wheel and source distribution builds also passed.

## CSS sibling selectors

Markup queries and cascade matching now support adjacent (`+`) and subsequent
(`~`) sibling combinators, including mixed child/descendant chains. Refresh builds
previous-element links separately for each document and parent, so text/comments
do not interrupt adjacency and unrelated documents cannot match as siblings.
Specificity counts type selectors on both sides of either combinator. Incomplete
combinator chains remain rejected. Behavior follows the
[W3C sibling-selector definitions](https://www.w3.org/TR/selectors-4/#adjacent-sibling-combinators).

Twelve cases cover element order, parent/document boundaries, mixed chains,
cascade specificity, invalid syntax and model-facing queries over edited markup
embedded in Python strings. Seven cases failed before implementation. All 269
local tests passed; after a pairwise-iteration lint correction, all 20 markup tests
passed again, with lint and formatting clear. This uses the static parsed element
tree, not browser DOM repair, dynamic mutation or layout evaluation.

The [native sibling-selector run](https://github.com/skanga/banger/actions/runs/34708298515)
at commit `ef0ea5637d8b41fa9b37657fad35c5b34d4880de` passed all six
Windows/Linux/macOS and Python 3.11/3.13 jobs, including tests, lint, formatting
and package builds. Local wheel and source distribution builds also passed.

## Call-query traversal scaling

Call-tree and shortest-path queries group resolved calls into adjacency lists
once per traversal. Path reconstruction uses predecessor links rather than copying
the accumulated path at each step. Detailed paths collect call sites by step in
one pass. This preserves full resolved closures, source order and per-site evidence;
it does not introduce a call-tree truncation limit or promote ambiguous edges.

On an indexed 200-function chain, forward/reverse trees dropped from 39,800 call
record visits each to 199; detailed paths dropped from 79,401 to 398. Observed
local timings were approximately 4.3 ms to 0.11 ms for trees and 8.5 ms to 0.27 ms
for detailed paths. Tests assert bounded record visits rather than machine-specific
timing thresholds. Three scaling cases failed before the change; a fourth checks
shortest branches, cycles and module-level sites. Existing path tests retain
duplicate-site, argument and return-holder evidence. All 257 local tests passed,
along with lint and formatting checks. These measurements isolate queries after
indexing and do not establish end-to-end performance on every repository.

The [native call-query run](https://github.com/skanga/banger/actions/runs/34707946884)
at commit `88dc14a0a14061a960a8f27bfb0d779f982613f9` passed all six
Windows/Linux/macOS and Python 3.11/3.13 jobs, including tests, lint, formatting
and package builds. Local wheel and source distribution builds also passed.

## Dependency graph node limits

The existing 1,000-node dependency graph limit is now enforced for each newly
visited node, including wide fanout. Traversal finishes processing retained nodes
and marks truncation only if a reachable node was actually omitted. A complete
graph of exactly 1,000 nodes is no longer incorrectly marked truncated. Edges to
omitted nodes are excluded so every returned endpoint has a returned node.

Six real-source cases cover backward fanout below, at and above the limit, plus
forward fanout at and above it. Three original backward cases failed before the
fix. All 253 local tests passed afterward, together with lint and formatting.
The limit applies to returned graph nodes; call-site listings and graph-building
memory are not bounded by this limit.

The [native graph-limit run](https://github.com/skanga/banger/actions/runs/34707636286)
at commit `6d6fa14e2a824b1b4e6ba988c810ce0a7d7109f1` passed all six
Windows/Linux/macOS and Python 3.11/3.13 jobs, including tests, lint, formatting
and package builds. Local wheel and source distribution builds also passed.

## Python expression dependency verification

Python flow expressions now use AST reads rather than matching words in source
text. Strings, attribute names, keyword labels and lambda/comprehension bindings
no longer create false dependencies on same-named outer variables. Lambda-local
assignment expressions are also distinguished from captured values. F-string
reads, lambda defaults and the outermost comprehension iterable retain their
dependencies. No expressions are executed by this analysis.

Seventeen cases cover these distinctions, nested lambdas, generator expressions
and Unicode names. Eight cases reproduced false dependencies before correction;
the others preserve real dependencies or verify related boundaries. The complete
local suite passed 247 tests, plus lint and formatting. This remains syntactic,
path-insensitive analysis, not proof that a closure executes or a branch runs.
Other languages retain lexical expression approximations.

The [native expression-scope run](https://github.com/skanga/banger/actions/runs/34707150033)
at commit `9f6e06ba8f859bfb80a7ab3e727284a1a0ba4523` passed all six
Windows/Linux/macOS and Python 3.11/3.13 jobs, including tests, lint, formatting
and package builds. Local wheel and source distribution builds also passed.

## Module-level flow isolation

Module values and expressions now include the source path in their graph identity.
Previously, the absent enclosing symbol made same-named module values share a
node, and equal expressions on the same line in separate files lost one source
location. Expression dependencies now include names assigned within the current
module, allowing return holders to flow through module assignments into calls.

Three failing-before/passing-after Python regressions cover module assignment and
call chains, unrelated files with matching variable names, identical expressions
in separate files, and return-holder source provenance. All 230 local tests passed,
along with lint and formatting checks. The graph remains path-insensitive and
does not resolve imported variable aliases or prove runtime assignment order.

The [native module-flow run](https://github.com/skanga/banger/actions/runs/34706772798)
at commit `43360656246f7b6fc6d3fb2b677c5875831e1c58` passed all six
Windows/Linux/macOS and Python 3.11/3.13 jobs, including tests, lint, formatting
and package builds. Local wheel and source distribution builds also passed.

## Python flow argument binding

Backflow call-site reports and graph edges now share signature-based Python
argument binding. This fixes keyword values attributed to omitted parameters,
positional-only parameters confused with same-name entries in `**kwargs`,
variadic parameters absent from queries, and shifted implicit receiver arguments.
Reports retain the single `argument` field and add all contributing `arguments`
plus binding evidence. Graphs preserve candidate call-resolution evidence.

Eleven cases cover keyword/default separation, keyword ordering, equality
expressions, variadic positional/keyword values, positional-only arguments,
dynamic splats, invalid calls, implicit receivers with nonstandard names, and
forward propagation through a variadic parameter. Six initial cases reproduced
incorrect or missing behavior; two additional cases established the expanded
report contract. The full local suite passed 222 tests; lint and formatting passed.
No expressions are evaluated. Default-expression origins, dynamic splat contents,
decorated signatures and language-specific binding outside Python remain gaps.

The initial native run passed all flow cases but exposed a Linux/Python 3.13
acceptance-test race: the approval modal was active before its button children
were mounted. The click helper now waits for mounting before checking layout.
All 13 local UI/end-to-end tests passed after this test-only correction.
The [final flow-binding run](https://github.com/skanga/banger/actions/runs/34683390044)
at commit `f5a418c09c21d3afb12de1c791c569473333e5a7` passed all six native
Windows/Linux/macOS and Python 3.11/3.13 jobs, including tests, lint, formatting
and package builds.

## Declared Python default origins

The index now preserves default expressions with their source path, line and
enclosing declaration scope. Backflow reports and graph edges expose these
origins only when signature binding proves an argument was omitted. Explicit
arguments, invalid calls and unresolved splats do not acquire default edges.
Five cases verify those boundaries plus multiline keyword-only defaults, `None`,
nested declaration scope and persistent index reload. All five failed before
implementation; the complete local suite passed 227 tests afterward, along with
lint and formatting. The index cache version was advanced to rebuild old entries.

These nodes identify declared source origins. They do not evaluate expressions
or prove the current value of a mutable default. The follow-up below extends
their upstream dependency traversal.

Default-dependency follow-up: backflow now traverses known bindings in the
default expression's declaration scope. Module assignments and enclosing
function parameters/local assignments are included, without confusing a caller's
same-named variable with the declaration binding. Repeated calls share one
default-expression dependency. Two new cases failed before implementation;
an additional assertion exposed missing multiline expression parsing and now
passes, including persistent index reload. Expression parsing restores grouping
around source fragments without evaluating them. The graph remains
path-insensitive: assignment order, imported/free-variable dependencies and
runtime mutations are not proven.

The default-dependency follow-up passed all 337 local Windows tests, Ruff lint
and formatting, and wheel/source-distribution builds. Commit
`98ffc93e978cb116dce83ba58094f96f82bc9eb2` passed all six native
Windows/Linux/macOS and Python 3.11/3.13 jobs, including tests, lint, formatting
and builds: [CI run 34714068737](https://github.com/skanga/banger/actions/runs/34714068737).

The [native default-origin run](https://github.com/skanga/banger/actions/runs/34703759760)
at commit `0a381653a1fb1214e177e2ff6e9fa257cf3599d7` passed all six
Windows/Linux/macOS and Python 3.11/3.13 jobs, including tests, lint, formatting
and package builds. Local wheel and source distribution builds also passed.
