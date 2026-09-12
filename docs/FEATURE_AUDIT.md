# Banger feature and verification audit

This audit preserves the user's target: an independent terminal coding agent with the best attempt at Benzi-equivalent capabilities. The working application is not proof of exact compiler parity.

| Requirement | Current evidence | Remaining limits or verification |
|---|---|---|
| Python + uv application in the current directory | Wheel installed into an isolated environment; launcher and live coding task passed using site-packages | Native Windows verification only |
| Independent implementation; mini-swe-agent optional | Banger source imports no Benzi/mini-swe-agent modules | No proprietary implementation available for differential comparison |
| Terminal UI; no graph | app.py, test_tui.py, test_end_to_end.py | Exported SVG exists; browser unavailable for visual inspection |
| Chat, source, diffs, tools, sessions, interrupt, mouse | Textual widgets and interaction tests | More terminal-size and cancellation UI checks desirable |
| All ten code languages | test_index.py language matrix | Parsing/basic calls are not complete language semantics |
| Cross-file bindings | test_cross_language.py; Python import tests | Advanced module systems, overloads, macros, dynamic dispatch remain partial |
| Definitions, callers, closure, paths, hierarchy, references, outlines | index.py, analysis.py, hierarchy.py, tools.py; query tests | Hierarchy resolves common Python, Java, C#, JS and TS bindings; remaining languages retain name candidates. References retain syntactic scope rather than full type binding |
| Forward/backward flow across calls | test_flow.py; dependency graph with resolution evidence | Path-insensitive; ambiguous edges remain candidates |
| Markup, CSS, DOM-JS, Python-embedded markup | test_markup.py | Conditional/browser-dependent rules, computed layout and exhaustive selector/cascade semantics not implemented |
| Syntax and semantic write gates | test_edits.py, test_batch_edits.py; combined validation for coordinated changes | Semantic gate covers known call regressions and Python signatures, not complete type checking |
| Impact and relevant tests | Matching before/after edit reports with callers, value consumers, and relevant tests; persisted by snapshot ID | Test selection can miss dynamically invoked tests; reports do not execute tests |
| Runtime tracing and static overlay | test_tracing.py; hash-validated runtime profile edges | Python only; traces are bounded and large/custom values are summarized |
| Generated reproductions and local execution | test_end_to_end.py, test_execution.py | Native cmd verified; native Linux/macOS bash still unverified |
| Undo and restart recovery | test_edits.py, test_state.py, test_batch_edits.py; grouped undo and incomplete-operation classification | Arbitrary shell changes are not captured by edit snapshots; multi-file writes are not filesystem-wide atomic |
| Persistent conversations, memory, index, trace, undo | StateStore, restart tests, context tests | Context excerpts are not a lossless in-context summary; exact history stays available on disk |
| Anthropic/OpenAI-compatible/local model interfaces | Mocked provider tests plus live OpenAI-compatible streaming/tool execution with gpt-5.3-codex-spark | Anthropic live endpoint unverified; local models must support tool calling |
| Escalation confirmation | test_agent.py, test_permissions.py | Stronger model is configured for the same provider/endpoint |
| Selectable familiar permission modes | Policy tests, TUI approval/mode-switch tests | Local execution has no filesystem/network sandbox |
| Windows/Linux/macOS with cmd/bash | Platform-specific executor and cross-platform workflow | Windows tested here; other native runners not yet run |
| Containers | Explicitly deferred by user | Later version |
| No headless agent/API/benchmark requirement | Only interactive application launcher | Internal Python modules exist for implementation/testing |

## Next verification gates

1. Full Windows suite passed: 158 tests; grouped-edit verification is included. Native CI results are recorded separately below when available.
2. Wheel and source distribution built; isolated Windows installation passed launcher and live agent checks.
3. Run the native Linux/macOS workflow; do not claim those results before they exist.
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
