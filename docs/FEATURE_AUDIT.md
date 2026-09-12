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
| Forward/backward flow across calls | test_flow.py, test_flow_arguments.py; shared Python signature binding and dependency graph with resolution evidence | Path-insensitive; ambiguous edges remain candidates; splats, decorated signatures and default-expression origins unresolved; other languages use positional approximations |
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

1. Full local Windows suite passed: 222 tests; ten-language edit acceptance, scoped semantic-gate regressions, compact-terminal interaction, grouped edits, single-file undo recovery, Python flow argument binding, shutdown recovery, C++ hierarchy and Git discovery are included. Native CI results are recorded separately below.
2. Wheel and source distribution built; isolated Windows installation passed launcher and live agent checks.
3. Native Windows, Linux and macOS CI passed on Python 3.11 and 3.13; see the recorded run below.
4. Live OpenAI-compatible coding task passed on 2026-09-11; see details below. Other providers remain covered by mocked tests.
5. Continue strengthening language and markup analysis where the current evidence is narrower than Benzi's described capability.

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
