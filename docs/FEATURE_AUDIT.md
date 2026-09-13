# Banger feature and verification audit

This audit preserves the user's target: an independent terminal coding agent with the best attempt at Benzi-equivalent capabilities. The working application is not proof of exact compiler parity.

| Requirement | Current evidence | Remaining limits or verification |
|---|---|---|
| Python + uv application in the current directory | Isolated Windows wheel installation and live coding task; native CI tests/builds on all three platforms | Installed-wheel live task was Windows only |
| Independent implementation; mini-swe-agent optional | Banger source imports no Benzi/mini-swe-agent modules | No proprietary implementation available for differential comparison |
| Terminal UI; no graph | app.py, test_tui.py, test_end_to_end.py; live installed-wheel TUI workflow and 120x40 SVG rendered and visually inspected; heading contrast and restored Markdown regression tests | Windows console and Linux/macOS PTY input/output acceptance passed; terminal-emulator pixel rendering remains unverified |
| Chat, source, diffs, tools, sessions, interrupt, mouse | Textual interaction tests, including 80x24 setup and approval controls | Windows console keyboard/mouse and process-restart checks passed; Linux/macOS PTY setup, mouse navigation and terminal cleanup passed; emulator-specific rendering remains unverified |
| All ten code languages | test_index.py query matrix; test_language_edits.py tool-level gates, impact and restart undo | These tests do not invoke every language's compiler or prove complete language semantics |
| Cross-file bindings | test_cross_language.py; Python import tests | Advanced module systems, overloads, macros, dynamic dispatch remain partial |
| Definitions, callers, closure, paths, hierarchy, references, outlines | index.py, analysis.py, hierarchy.py, tools.py; query tests | Hierarchy resolves common Python, Java, C#, JS and TS bindings plus same-file C++ lexical bases, Ruby constant namespaces, Rust supertraits and Go declared embedding; other forms retain candidates or unknowns. References retain syntactic scope rather than full type binding |
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

1. Full local Windows suite passed: 620 tests with two POSIX-only skips; ten-language edit acceptance, scoped semantic-gate regressions, compact-terminal interaction, grouped edits, single-file undo recovery, repeated tool-ID recovery, Python flow argument binding and default origins, module flow isolation, expression scopes, graph limits, call-query scaling, CSS sibling/attribute selectors and source provenance, embedded literal source maps, dynamic template uncertainty, shutdown recovery, C++ hierarchy and Git discovery are included. Native CI results are recorded separately below.
2. Wheel and source distribution built; isolated Windows installation passed launcher and live agent checks.
3. Native Windows, Linux and macOS CI passed on Python 3.11 and 3.13; see the recorded run below.
4. Live OpenAI-compatible coding task passed on 2026-09-11; see details below. Other providers remain covered by mocked tests.
5. Continue strengthening language and markup analysis where the current evidence is narrower than Benzi's described capability.

## Requirements review and documentation reconciliation

The requirement review preserves the agreed scope: an independent uv/Python TUI,
the ten requested languages and markup, structured queries, gated edits and undo,
local execution and Python tracing, durable state, both model protocols, selectable
permissions and mandatory escalation approval. Graph UI, integrated editing and
container execution remain governed by the user's recorded exclusions/deferrals.

The README was reconciled with current source and the existing regression evidence.
It now describes Python imported-value flow, parsed DOM literal candidates, local
CSS imports and stylesheet applicability, readable edit proposals, restored chat
formatting, and bounded runtime values and lifecycle events. An obsolete statement
that imported variable aliases were not resolved was removed. DOM selectors that
cannot be resolved are explicitly described as potentially absent from results;
the documentation no longer implies that every dynamic selector gets a warning.

Remaining work is not inferred solely from test counts. At this review, async
generators were excluded from the runtime exit classifier; the subsequent
async-generator checkpoint below implements and verifies that behavior. Static binding, hierarchy and flow depth still vary by
language; the basic ten-language fixtures do not prove exhaustive semantics.
Native terminal-emulator behavior and live Anthropic compatibility remain separate
verification gaps. Existing headless/native-runner and live local-provider evidence
does not establish either one. These distinctions keep completion unproven.

This review changes documentation only. The application remains at the code
verified by the 510-test native run recorded below; no new execution or model
compatibility result is claimed from the documentation update.

## Search previews and original-source columns

Long matching lines previously returned only their first 2,000 characters, which
could omit the matched text. Previews now include context around the first match
and retain the 2,000-character bound. Results include 1-based source character
columns, an exclusive end column, and the preview's starting column. Case-folded
literal matches map back to original-source offsets even when a character expands
during folding, such as sharp-s. Regex offsets already refer to source characters.

Three regressions first failed because long-line previews omitted the match.
They now cover literal, Unicode case-folded and regex queries, snippet/source
agreement and column positions. All 11 search tests passed. Matches larger than
the preview can still be truncated; the source span and truncation marker remain
available for targeted inspection.

## Bounded regular-expression search

`search_text` now accepts `regex=True` for Python regular expressions over physical
UTF-8 lines. Literal search remains the default. Regex mode preserves discovery,
file/byte/result limits and uses Python's case-insensitive matching when requested.
A trusted isolated-interpreter worker receives JSON data, with a 10-second deadline;
timeout terminates the worker and returns an explicit error instead of claiming
an empty result. Windows job ownership and POSIX process groups cover worker
descendants. Cancellation through the existing blocking-tool wrapper waits for
the bounded worker to finish; partial regex matches are not returned on timeout.

Two initial tests failed on the missing regex argument. A third failing test
exposed a phantom final line in the shared line splitter; empty files and trailing
newlines now have correct physical-line behavior. Eight search tests passed,
covering ordinary/invalid regex, a pathological backtracking pattern, physical
line boundaries and existing literal search. An installed-wheel smoke check also
passed with the isolated worker, without making a model request.

The full local suite passed 620 tests with two expected POSIX-only skips in 96.23
seconds. Lint, formatting and package builds passed. Commit
`c4a526227146cdb58c35bc6378289db3b6cc70a0` passed all six native
Windows/Linux/macOS jobs on Python 3.11 and 3.13 in
[CI run 34749073583](https://github.com/skanga/banger/actions/runs/34749073583).
This run also includes the dependency-listing and lifecycle-test changes below.

## Static declared dependency listing

The independent `list_dependencies` tool reads recognized manifests through
workspace discovery, without running package managers or evaluating build code.
It extracts Python project/build/development groups and requirements lines,
Node dependency groups, Cargo dependency tables (including nested target/workspace
tables), Go require declarations, Maven dependency elements and NuGet package
references/versions. Results preserve source paths, groups, raw version expressions
and .NET ancestor attributes such as conditions.

The result explicitly describes declarations rather than installed or resolved
dependencies. Includes, conditions, workspace inheritance, properties, overrides,
transitive dependencies and lockfile resolution are not evaluated. Recognized
unsupported manifests, such as Gemfile and executable build files, and malformed
or oversized manifests are reported as unresolved. Discovery is bounded to 100
recognized manifests, 1 MiB per file and 4 MiB read per query; truncation is explicit.
This is not an exhaustive recognizer for every dependency format.

Ten tests cover seven manifest forms, malformed and executable inputs, Python
group includes, nested-project refresh, conditional .NET references and size
limits. Eight initial cases failed because the tool was missing. A direct check
on Banger found its runtime, development and build groups without unresolved
files or truncation. Other language-analysis and search-depth gaps remain open.

The full local suite passed 617 tests with two expected POSIX-only skips in
88.82 seconds; lint, formatting and builds passed. Initial CI passed the dependency
tests on every platform, but Windows 3.13 failed an existing inherited-output-pipe
test whose 0.2-second deadline could kill the parent wrapper before normal exit.
The fixture now separates parent startup from a 30-second descendant lifetime,
with a 5-second command deadline and 10-second outer bound. It explicitly checks
normal Windows job cleanup versus POSIX group cleanup at timeout. All 19 local
execution/dependency tests passed after this test-only correction.

The corrected lifecycle test and dependency listing passed all six native jobs in
the later [CI run 34749073583](https://github.com/skanga/banger/actions/runs/34749073583),
which contains commit `bd43afb36bf49a1759d537a83002a01942e22162`.

## Independent built-in reference help

Recorded reference-agent calls use `read_reference` with language and artifact
topics; the checkout does not expose that tool's implementation. Banger now
provides its own independently written reference help for overview, languages,
artifact recovery and tool contracts. Language extensions come from the actual
parser mapping, and tool contracts come from the actual registered schemas.
Help explicitly identifies Python-only tracing, static-analysis uncertainty,
markup limits, recovery tools and the limits of snapshot undo.

Two regressions first failed because the tool was absent. They now verify
language extensions, Python-only tracing, discoverable topics, exact agreement
with registered tool schemas, callable recovery-tool names and rejection of an
unknown topic. The tool requires no network or project execution and is available
in read-only mode. Dependency listing remains a separate capability gap; this
does not claim exact equivalence to the unavailable reference implementation.

Local verification passed 607 tests with two expected POSIX-only skips in 64.08
seconds. Lint, formatting and builds passed. Commit
`7afd8043794f9f6100c07694d5254ef08655c500` passed all six native
Windows/Linux/macOS jobs on Python 3.11 and 3.13 in
[CI run 34748443227](https://github.com/skanga/banger/actions/runs/34748443227).

## Persistent conversation plans

The independent `update_plan` and `get_plan` tools provide session-scoped plans.
An update atomically replaces the current validated steps and explanation in
the artifact store. Plans allow pending/in_progress/completed statuses and at
most one active step, with up to 20 steps of 500 characters and a 2,000-character
explanation. Empty lists clear the plan. This is conversation state available
in every permission mode, rather than an edit to project source or project facts.

The agent includes the current saved plan as data in each model turn, so context
shortening does not remove the current plan and resuming does not pick up another
conversation's plan. Updates use the existing Tools result display. A local
100x32 capture was rendered and visually inspected; three steps, their statuses
and the explanation were readable. The raw capture remains local.

Ten tests cover persistence, isolation, status progression, clearing, invalid
JSON/shape/status, multiple active steps, size limits, missing sessions, and a
resumed model request containing the saved plan. Nine initial cases failed on
the missing tools/context. The full local suite passed 605 tests with two expected
POSIX-only skips in 63.75 seconds. Lint, formatting and builds passed after test
import whitespace was corrected. Other capability gaps remain open.

Commit `b9413c06facce4e92c35238c1652044ee9ab2b54` passed all six native
Windows/Linux/macOS jobs on Python 3.11 and 3.13 in
[CI run 34748209021](https://github.com/skanga/banger/actions/runs/34748209021).

## Removal of stale project facts

The independent `forget_fact` tool removes a saved project fact by exact key and
reports whether a row existed. It follows the same memory-edit policy as
`remember_fact`: read-only denies removal, ask mode waits for approval, and
accept-edits allows it. Parameterized SQL preserves unrelated keys and the
committed removal survives database reopening. Conversation history is not
erased; subsequent model turns read the updated current fact collection.

Four regressions cover exact-key removal (including SQL-looking text), repeated
removal, retention of other facts, reopening, read-only denial, ask-mode denial
and approval. Three initially failed because the tool was missing. Targeted
state and permission checks passed 18 tests. Planning and the other tool-inventory
gaps remain separate work.

Local verification passed 595 tests with two expected POSIX-only skips in 63.14
seconds. Lint, formatting and builds passed. Commit
`51d92e858ed972570b40075e99ec276f69a592d5` passed all six native
Windows/Linux/macOS jobs on Python 3.11 and 3.13 in
[CI run 34747911733](https://github.com/skanga/banger/actions/runs/34747911733).

## Read-only project text search

The reference's recorded tool sequences expose project text search in addition
to declaration search. Banger previously required broad reads or an approved
shell command for this workflow. The independent `search_text` tool now searches
literal text in discoverable UTF-8 workspace files, with file/directory scope,
case-sensitive or Unicode case-folded matching, physical line numbers, and bounded
line previews. It is available in read-only mode and uses the existing Git-ignore,
excluded-directory and symlink discovery policy.

Five tests cover literal punctuation, CR/LF line numbering, Git ignores,
directory scope, binary input, invalid requests, result limits, Unicode case
folding, oversized files and preview truncation. Three initial tests failed on
the missing tool. Limits are explicit: 2 MiB per file, 32 MiB read and 10,000
discovered files per search, 200 results, 2,000 characters per preview, and 200
reported skipped paths plus the total skipped count. Regex support was added in the later bounded-search milestone. A skipped file is not evidence that its contents contain no matches.

Local verification passed 591 tests with two expected POSIX-only skips in 64.26
seconds. Lint, formatting and builds passed after correcting blocking Git setup
in the new async test. Commit `69f184f2e380ec644fd2dcc1736de6f42732684d`
passed all six native Windows/Linux/macOS jobs on Python 3.11 and 3.13 in
[CI run 34747649108](https://github.com/skanga/banger/actions/runs/34747649108).

A tool-name-only scan of the recorded benchmark sequences also identified
`update_plan`, `forget`, `read_reference`, and `list_dependencies` for subsequent
behavior review. The earlier 16-name README inventory was a sample, not a
complete tool inventory. Graph-selection tools remain outside the agreed TUI
scope. No reference implementation, prompts or fixture code were copied.

## Current-wheel live TUI acceptance

On 2026-09-13 the current wheel was installed into the isolated Windows acceptance
environment. Every installed Banger Python module matched the workspace source
byte-for-byte. The application source was commit
`7cfa5191179aa4102a28125a5330009689661a39`; the wheel SHA-256 was
`26ff1e2962fb7572230220410a01146da7437cbbd71291954323398ea372c925`.

A live OpenAI-compatible session with the user-selected local model ran through
Textual's test driver at 120x40. With ask mode selected, it queried definitions
and callers, read the fixture, obtained command approval, reproduced a failing
fee calculation, obtained edit approval, applied the fix, and obtained command
approval to verify it. The independent verification file stayed unchanged.
Captured runtime events proved both variadic argument sets, two await
suspension/resumption pairs, and final results of 6 and 4. No model escalation
occurred and the configured API key was empty.

Diff/tool widgets contained output and source widget contents matched the edited
file. A second app instance recovered the saved conversation exactly in read-only
mode and completed a live follow-up summary. Both model clients closed cleanly.
The completed-chat SVG was rendered locally and visually inspected: prompt,
response, headings, navigation and controls were readable at the captured size.
This is installed-wheel live model/TUI-driver evidence; native terminal transport
remains covered by the separate Windows console and POSIX PTY checks below.
Raw captures and conversation history remain local.

## Custom type capture without metaclass callbacks

Runtime value capture previously used set membership for exact-type checks and
ordinary class attribute access for type names. These operations could invoke
custom metaclass hashing, equality, attribute access, or descriptors inside the
trace hook, allowing capture to interrupt an otherwise valid target program.
Exact-type checks now use identity, and type names/modules use built-in type
descriptors directly. Exception-name capture follows the same rule.

Five subprocess regressions first reproduced failures for custom hashing,
equality with a deliberate hash collision, attribute access, a name descriptor,
and an exception class's name descriptor. They now verify successful execution
and the original argument/return type summaries or handled exception name.
Existing async-generator and large-value capture tests also passed. This covers
these metadata callbacks, not arbitrary interpreter instrumentation interference.

Local verification passed 586 tests with two expected POSIX-only skips in 63.67
seconds; lint, formatting and wheel/source builds passed. Commit
`7cfa5191179aa4102a28125a5330009689661a39` passed all six native
Windows/Linux/macOS jobs on Python 3.11 and 3.13 in
[CI run 34747201480](https://github.com/skanga/banger/actions/runs/34747201480).

## Dictionary trace capture allocation

Dictionary capture previously materialized every dictionary entry before keeping
its first ten. A regression with 300,000 entries measured 19,199,352 bytes of
temporary allocation despite returning only ten entries. Capture now iterates
only the first ten entries; the same local measurement used 1,080 bytes.
The subprocess regression permits up to 200,000 bytes to accommodate runtime
differences while rejecting allocation proportional to the input dictionary.

Additional checks preserve the existing treatment of non-string keys and verify
that a traced program retains the original 100,000-entry dictionary, returns its
identity, and saves/restores the sampled argument and return values exactly.
This bounds entry sampling work; it does not establish a total trace byte limit
or change the representation of dictionary keys.

Local verification passed 581 tests with two expected POSIX-only skips in 63.34
seconds; lint, formatting and wheel/source builds passed. Commit
`1ce3c5333b1cd69fca5bf30565f42e8889e92935` passed all six native
Windows/Linux/macOS jobs on Python 3.11 and 3.13 in
[CI run 34746940309](https://github.com/skanga/banger/actions/runs/34746940309).

## Go declared embedding

Go type hierarchy queries now preserve embedded struct fields and interface type
elements, excluding named fields and method declarations. Pointer and generic
expressions retain their source spelling. Nominal links use matching package names
and directories, or project-module imports with explicit aliases or the imported
package's declared name. Each link identifies its relationship as embedding;
the existing reverse `subclasses` collection represents reverse embedding here.
Constraint unions stay whole and unresolved. This does not infer method promotion,
implicit interface satisfaction, type aliases, generic constraints, or Go workspace
and nested-module build configuration.

Fourteen tests cover these forms, reverse links, persistence, refresh, duplicates,
different packages, build directives, missing qualifiers, type-parameter shadowing,
dot imports and local scopes. Nine initial tests failed because embedding lists
were absent. Files with build directives or underscores in their filename remain
conservative candidates because build selection is not evaluated; local block
declarations remain unknown. The persisted index cache advances to `files-v21`.

Local verification passed 578 tests with two expected POSIX-only skips in 67.07
seconds. Ruff lint and formatting checks and wheel/source builds passed. The
installed Go 1.26.5 compiler also accepted an isolated fixture with pointer,
generic and interface embedding, with dependency downloads disabled.

Commit `2aabbde979eb7440e19981036851cec5cfdd7154` passed all six native
Windows/Linux/macOS jobs on Python 3.11 and 3.13 in
[CI run 34746671614](https://github.com/skanga/banger/actions/runs/34746671614).

## Rust declared supertraits and tool inventory review

The 16 tool names sampled in the reference README each have a corresponding
Banger tool method. This verifies inventory correspondence, not complete
behavioral parity: runtime tracing remains Python-specific, and static resolution
depth differs by language. Reviewing hierarchy behavior exposed Rust traits whose
supertrait lists were empty despite explicit declarations.

Rust hierarchy queries now extract direct trait bounds and `where Self` bounds,
preserve generic expressions, and exclude lifetime and generic-parameter-only
bounds. Same-file local/block scopes, inline modules, self/super/crate paths and
simple explicit aliases carry resolution evidence. Nested modules do not inherit
unqualified outer-module item names. Attributed or duplicate traits remain
ambiguous; type-parameter shadowing remains unknown. Matching external-file trait
paths remain candidates until module mapping is proven. The index cache advances
to `files-v20` so persisted projects rebuild this metadata.

Thirteen regressions cover declaration order, generic and Self bounds, lifetime
exclusion, inline modules, parent/root paths, aliases, attribute uncertainty,
duplicates, non-trait names, type parameters, cross-file candidates, restart and
refresh. Ten initial cases failed on missing supertrait lists; two review cases
then exposed shadowing and missing external-file candidates. Rust trait `impl`
relationships, Cargo targets/module declarations, grouped/glob/re-export expansion,
macro expansion and compiler constraint validation remain incomplete.

Local verification passed 564 tests with two expected POSIX-only skips in 63.46
seconds. Ruff lint and formatting checks and wheel/source builds passed.
Commit `234be43b396df7da72f9a9e7bfe69335f4763e2a` passed all six native
Windows/Linux/macOS jobs on Python 3.11 and 3.13 in
[CI run 34746151617](https://github.com/skanga/banger/actions/runs/34746151617).

## Parameterized superclass and interface declarations

Java, C# and TypeScript hierarchy queries now separate the complete source base
expression from its nominal declaration name using syntax-tree nodes. Imported
and qualified generic bases and interfaces resolve without discarding displayed
type arguments. C# filters same-name declarations by type-parameter count, while
Java raw bases can still refer to generic declarations. Java/C# type parameters
that shadow a class name remain unknown rather than linking a global class.
The persisted index advances to `files-v19` for the new metadata.

Eleven regressions cover nested argument syntax, imported aliases and namespaces,
interface inheritance, C# generic/non-generic overloads, wrong argument count,
Java raw types, import ambiguity, computed TypeScript bases, parameter shadowing,
restart and refresh. Five initial cases failed before implementation; two review
cases then exposed type-parameter shadowing. These are nominal declaration links,
not instantiated generic types or proof that the code satisfies compiler type
constraints. Qualified nested generic owners, alias expansion and full language
type checking remain outside this checkpoint's verified behavior.

Local verification passed 551 tests with two expected POSIX-only skips in 60.25
seconds. Ruff lint/format checks and wheel/source builds passed.

Commit `b93ae30335f71260ded2d3df8cb232987b401597` passed all six native
Windows/Linux/macOS and Python 3.11/3.13 jobs, including tests, lint, formatting
and package builds:
[CI run 34745662368](https://github.com/skanga/banger/actions/runs/34745662368).

## Native Linux and macOS terminal acceptance

`test_terminal_posix.py` launches the normal interactive application with stdin,
stdout and stderr attached to a real POSIX PTY. It runs at both 80x24 and 120x40.
Terminal keystrokes verify the missing-permission validation and explicit read-only
selection. Terminal mouse sequences open the fixture source and session list;
the permission picker opens and cancels by keyboard. The process exits with code
zero, leaves the alternate screen, restores the original terminal attributes,
and preserves fixture source bytes. The test requires no model credentials and
does not submit a model request. Child processes and descriptors have bounded
cleanup on failure.

Commit `65cb875f29fb6f0d3c71c4ed6bce3b5b957f05da` passed all six native CI jobs.
The logs explicitly show both PTY cases executed under Linux and macOS on Python
3.11 and 3.13: each POSIX runner passed 542 tests. Both Windows runners passed
540 tests and skipped these two POSIX-only cases; Windows console acceptance is
recorded separately below. Lint, formatting and package builds passed throughout:
[CI run 34745195748](https://github.com/skanga/banger/actions/runs/34745195748).

This establishes native console transport, basic interaction and cleanup on all
three operating systems. It does not prove every terminal emulator's pixel
rendering, POSIX live-model tasks or exhaustive terminal interaction sequences.
The application code is unchanged from the compact-wrapping checkpoint.

## Native Windows console acceptance and compact wrapping

A real Windows console PTY reported terminal-backed stdin/stdout at 80x24.
Banger's normal interactive launcher was driven with keyboard and terminal mouse
input in an isolated fixture. Setup selected read-only mode; the authorized local
OpenAI-compatible model used query/file tools and correctly reported the fixture
function's return value. The exact prompt and eight-message tool conversation
persisted, and the source stayed unchanged. The permission picker opened and
cancelled by keyboard; mouse input opened source and session panes. A fresh
process restored the saved conversation through the session list. Three native
runs exited cleanly with code zero.

The first native replay exposed truncated middle words in narrow chat panes:
RichLog's default 78-column floor exceeded the available width. Eight regression
cases now verify visible user, restored-user, assistant and tool text at 80x24,
both directly and after shrinking from 120x40. The original three tests failed
on missing visible words; subsequent tests exposed hidden-tab and resize cases.
WrappedLog retains renderables for reflow and waits for a usable pane width when
hidden. A corrected native replay displayed the complete restored prompt and
answer. A separate compact SVG was rendered and visually inspected locally.

The full local suite passed 540 tests in 62.64 seconds, plus Ruff lint/format and
wheel/source builds. Raw console chunks, screenshots, fixture state and the live
report remain local. This is console transport and interaction evidence, not a
pixel capture from every terminal emulator. At that checkpoint, Linux/macOS native PTY interaction remained unverified; the
subsequent POSIX acceptance above closes basic interaction and cleanup coverage.
Terminal-specific rendering and live Anthropic compatibility remain unverified.

Commit `83b68c90c2b8198b5c01112fa74c7e437852cc04` passed all six native
Windows/Linux/macOS and Python 3.11/3.13 jobs, including all 540 tests, lint,
formatting and package builds:
[CI run 34744952074](https://github.com/skanga/banger/actions/runs/34744952074).

## Ruby superclass constant bindings

Hierarchy queries now retain complete Ruby superclass expressions, including
qualified and absolute constant paths. Local preceding declarations resolve
through lexical class/module nesting. Qualified class declarations preserve
Ruby's distinct lexical nesting rather than treating the namespace path as
additional lexical scopes. This follows the documented distinction in
[Ruby's module/class syntax](https://docs.ruby-lang.org/en/3.4/syntax/modules_and_classes_rdoc.html).

Eighteen tests cover top-level and nested bases, namespace shadowing, absolute
paths, qualified class declarations, computed bases, reassignment, conditional
and reopened declarations, mixins, inherited-constant uncertainty, cross-file
candidates and persisted refresh. Nine initial tests failed before implementation;
two review regressions then exposed global fallback and lost cross-file candidates.
The index cache advanced to `files-v18` to rebuild persisted Ruby metadata.

This does not execute Ruby or prove runtime loading, alias expansion, inherited
constant lookup, mixin ordering, autoload or metaprogramming. Those relationships
remain candidates or unknowns. No Ruby interpreter is installed locally, so the
fixtures establish static query behavior rather than execution equivalence.

Verification: 532 local Windows tests passed in 48.95 seconds. Ruff lint and
format checks passed after a test-only parentheses correction; all 18 Ruby tests
were rerun successfully. Wheel and source distribution builds passed. Commit
`a34b5d7988f010e5aa498a195187081a19c1192d` passed all six native
Windows/Linux/macOS and Python 3.11/3.13 jobs, including tests, lint, formatting
and builds: [CI run 34744242745](https://github.com/skanga/banger/actions/runs/34744242745).

## Async-generator runtime lifecycle

Async generators now retain invocation identity across awaits and direct yields.
The tracer distinguishes suspension, resumption, yielded values, normal completion
and exceptional exits. Direct yields use CPython's internal wrapper described in
[PEP 525](https://peps.python.org/pep-0525/#implementation-details); GC traversal
extracts its payload without calling user representation methods or reading raw
memory. An unexpected wrapper payload shape is recorded as unavailable.

Four subprocess regressions cover await/yield/asend and persisted trace restart,
explicit closure, cancellation while awaiting, and athrow recovery with None and
custom-object yields. The original two lifecycle tests failed before the change.
This implementation depends on CPython instruction and wrapper details; other
Python implementations and versions require separate verification.

Verification: 514 local Windows tests passed in 48.94 seconds, with Ruff lint,
format checks and wheel/source builds. Commit
`c29f47b5c99a5f431470e3891774773b246dd91d` passed all six native
Windows/Linux/macOS and Python 3.11/3.13 jobs, including tests, lint, formatting
and builds: [CI run 34743865658](https://github.com/skanga/banger/actions/runs/34743865658).

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

## Bounded large integer trace values

Runtime tracing summarizes integers larger than 1,024 bits using type, bit length,
sign and an explicit truncation flag. Smaller integers remain exact. This avoids
decimal conversion of enormous values when serializing the trace, including
values inside the supported list/dictionary depth.

Two real subprocess regressions first showed a successful program ending with a
tracer failure because a 5,001-digit positive or negative integer exceeded Python's
serialization limit. They now verify successful execution, argument/return
summaries, subsequent ordinary values and persisted trace recovery. A third case
covers nested large values and exact preservation at the 1,024-bit boundary.

Verification: 510 local Windows tests passed, with Ruff lint/format checks and
package builds. Native [CI run 34743256962](https://github.com/skanga/banger/actions/runs/34743256962)
at application commit `191599dc253240c1a101a32f49d06b9325e13e40` passed all six
Windows/Linux/macOS × Python 3.11/3.13 configurations, including tests, lint,
format and builds. No live-model check was added for this serialization fix.

The original program's integer values are unchanged; only recorded summaries are
bounded. This does not remove the tracer's other event, collection and depth limits.

## Ordinary function exception exits

Runtime traces classify exceptional exits from ordinary Python functions as
`unwind`, without a fabricated successful return value. The existing instruction
classification now applies to ordinary functions as well as synchronous
generators and native coroutines. Async-generator classification remains separate.

Six real subprocess cases cover explicit exceptions, arithmetic failures and
failed name lookup propagating through a caller, plus caught exceptions with an
explicit None return, an implicit return, or a return from finally. The initial
three failure cases incorrectly produced return events before the fix; handled
exception cases continue to preserve actual return values.

Verification: 507 local Windows tests passed, with Ruff lint/format checks and
package builds. Native [CI run 34743057376](https://github.com/skanga/banger/actions/runs/34743057376)
at application commit `a498b169d6e3efdb7950348c9185c4a12b3a5093` passed all six
Windows/Linux/macOS × Python 3.11/3.13 configurations, including tests, lint,
format and builds. No additional live-model check was run for this trace change.

This is CPython trace evidence, subject to the existing event/value bounds. It
does not add support for other language runtimes or async-generator suspension.

## Readable edit proposals

Ask-mode proposals for file writes and grouped edits now display labeled full
content with real line breaks. Exact replacements show separate old/new text
blocks, and grouped deletions display an explicit deletion label. This uses the
already supplied proposal, with no file reads introduced before authorization.
The proposal is shown as literal text in the read-only approval widget.

Four TUI regression cases first failed on escaped JSON or a null deletion value.
They cover writes, replacements, grouped writes and grouped deletions, verify
that the original file is unchanged while approval is pending, and deny each
proposal to verify no write occurs. Existing grouped-edit and provider workflow
tests also passed. A synthetic replacement dialog was rendered and visually
inspected; captures remain local. This is a readable proposal, not a computed
pre-edit diff or a change to authorization policy.

Verification: 501 local Windows tests passed, with Ruff lint/format checks and
package builds. Native [CI run 34742785291](https://github.com/skanga/banger/actions/runs/34742785291)
at application commit `50a854b0b7281e14f6b7312a997350070ae1c582` passed all six
Windows/Linux/macOS × Python 3.11/3.13 configurations, including tests, lint,
format and builds. The proposal changes were visually checked with a synthetic
TUI fixture, without another live-model request.

## Readable Markdown in new and restored chat

Assistant messages use a scoped Markdown renderer with bright, non-dim heading
colors suited to the dark chat surface. All six heading levels preserve their
formatting. Restored assistant messages use the same renderer as new responses;
user messages remain literal text. The theme override is scoped to rendering
instead of changing the application's shared console theme permanently.

Two TUI regression cases first failed for dark heading colors and raw Markdown
in restored messages. They now check all six rendered heading levels for visible
contrast and formatting through both new-message and session-selection paths.
A synthetic restored conversation was captured and visually inspected, including
headings, emphasis, inline code and lists. Captures remain local. Native terminal
emulator rendering is still outside this headless visual check.

Verification: 497 local Windows tests passed, plus Ruff lint/format checks and
package builds. Native [CI run 34742518909](https://github.com/skanga/banger/actions/runs/34742518909)
at application commit `be4f72529eeb854f38ca06dea39781d0b0fe3da0` passed all six
Windows/Linux/macOS × Python 3.11/3.13 configurations, including tests, lint,
format and builds. This renderer fix was checked with synthetic TUI responses;
the earlier live task supplied the visual defect that prompted it.

## Live installed-wheel TUI acceptance

The current installed wheel passed a Windows acceptance task through Textual's
120x40 headless driver using the user-selected OpenAI-compatible local model.
The live task exercised setup, Ask-mode edit and execution approvals, correction
of a Python calculation, and successful execution of an unchanged verification
file. Recorded traces confirmed variadic inputs, coroutine suspension/resumption
and final values.

After application shutdown, the Sessions tab restored the exact saved history.
A subsequent live request in Read-only mode correctly summarized the earlier
fix and verification. Both application instances closed their HTTP clients.
Diff/tool views and source-widget content were checked. Captured approval, diff,
completed and resumed screens were visually inspected; raw captures and detailed
reports remain local and are not included in this repository.

The visual issue found here (poor heading contrast and raw restored Markdown)
was corrected by the subsequent rendering work above. This single live Python task does not prove live
Anthropic compatibility, native-terminal rendering, or complete static-analysis
parity. Application source is unchanged; the 495-test native matrix remains the
applicable code verification.

## Coroutine trace lifecycle

Native Python coroutines now retain invocation IDs across `await` suspension.
Their trace records use `suspend` and `resume` rather than fabricated returns and
fresh calls. A propagated cancellation produces `unwind` without a return value;
handled cancellation can suspend again and ultimately return normally. An await
that completes immediately adds no suspension event.

Five real subprocess cases cover repeated awaits, propagated and recovered
cancellation, immediately completed awaits, and concurrent invocations. Runtime
child-call links survive resumption and state-store restart. The initial three
cases failed with false returns or extra invocation records before the fix.

Verification: 495 local Windows tests passed, with Ruff lint/format checks and
wheel/source builds. Native [CI run 34741932379](https://github.com/skanga/banger/actions/runs/34741932379)
at application commit `ceb2b18426dbcbfe201f246804c6acdbc3c805a7` passed all six
Windows/Linux/macOS × Python 3.11/3.13 configurations, including tests, lint,
format and builds. No additional live-model check was run for this trace change.

This extends the existing CPython instruction-based classification to native
coroutines. Async-generator suspension and yielded-value wrappers remain
unresolved. Internal exception events from the Python trace hook remain visible;
they do not necessarily mean an exception escaped the coroutine.

## Synchronous generator trace lifecycle

Python runtime traces distinguish synchronous generator `yield`, `resume`, final
`return` and exceptional `unwind` events. A suspended invocation keeps its frame
identity across resumption instead of appearing as a new call each time. Closing
a delegated generator does not manufacture a successful return value.

Four real subprocess cases cover send values, explicit final returns, `yield from`
and close, caught exceptions injected with `throw`, distinct invocations, and
runtime child-call overlays recovered from persisted traces. The initial two
cases failed because yields were recorded as returns and frame IDs changed.

Verification: 490 local Windows tests passed, with Ruff lint/format checks and
wheel/source builds. Native [CI run 34741701667](https://github.com/skanga/banger/actions/runs/34741701667)
at application commit `7de91b029e1e8479486d5cc6d048fc420d1fcde3` passed all six
Windows/Linux/macOS × Python 3.11/3.13 configurations, including tests, lint,
format and builds. No live-model check was added for this trace-event change.

The classifier accounts for the CPython instruction positions observed under
tracing. At this checkpoint the work did not distinguish coroutine/async-generator suspension,
infer completion when the interpreter emits no terminal event, or establish
equivalent bytecode behavior in other Python implementations. Resume events do
not themselves add new runtime call edges; child calls retain their generator
parent. Existing trace bounds still apply.
Native coroutine handling is covered by the subsequent work above.

## Variadic Python runtime arguments

The standalone runtime tracer now captures `*args` and `**kwargs` alongside
positional-only, ordinary and keyword-only arguments. It uses the executing code
object's argument flags, so local variables are not mistaken for inputs. Existing
bounded value summaries apply to the new groups as well.

Five subprocess regression cases cover each variadic group, mixed/default/empty
signatures, restart persistence, and method arguments containing custom objects.
The four signature cases first failed because variadic argument entries were
missing. Custom objects retain type summaries without invoking their `repr`;
long positional groups retain the existing ten-item limit.

Verification: 486 local Windows tests passed, with Ruff lint/format checks and
wheel/source builds. Native [CI run 34741392883](https://github.com/skanga/banger/actions/runs/34741392883)
at application commit `8a73d48ad32cca1ca7c78039790eb5d3ff9b8d7e` passed all six
Windows/Linux/macOS × Python 3.11/3.13 configurations, including tests, lint,
format and builds. No additional live-model check was run for this tracer change.

This improves Python runtime evidence only. It does not extend tracing to other
languages or remove the existing event, depth and value-size limits.

## Constant JavaScript DOM literals

DOM references decode ordinary string escapes and constant untagged templates,
including hexadecimal/Unicode escapes, paired UTF-16 surrogates, escaped CSS
backslashes and line continuations. Literal bracket method access and optional
calls work in JS/JSX/TS/TSX. This is literal decoding, with no source execution.
The rules follow the [ECMAScript string-literal specification](https://tc39.es/ecma262/multipage/ecmascript-language-lexical-grammar.html#sec-literals-string-literals).

`test_dom_literals.py` adds 26 cases: 21 literal values, four language variants
of bracket/optional calls, and invalid/dynamic boundaries. Seventeen initially
failed with missing references; the existing negative case passed. All 21 literal
fixtures also matched Node.js 24.20.0 in a separate controlled Windows comparison.
Node is not an application dependency and is not used to analyze user source.

Verification: 481 local Windows tests, Ruff lint/format checks and wheel/source
builds passed. Native [CI run 34741184249](https://github.com/skanga/banger/actions/runs/34741184249)
at application commit `c2a690644f7c81715b9b464ce1e98c9e4b1209bf` passed all six
Windows/Linux/macOS × Python 3.11/3.13 configurations, including tests, lint,
format and builds. This change has no additional live-model verification.

Interpolated/tagged templates, nonliteral expressions and legacy numeric escapes
remain unresolved. Receiver identity and runtime execution remain unproven.

## Parsed DOM-reference candidates

DOM-reference queries now inspect JavaScript/JSX and TypeScript/TSX call nodes
instead of matching raw source text. Inline JavaScript in HTML and extracted
Python markup uses the same parser; Python literal source maps preserve the
original source line. Comments, string examples, longer unrelated method names,
HTML text, JSON script blocks and ignored bodies of external scripts no longer
produce references. Results explicitly identify themselves as syntactic candidates.

Nine regression cases cover these boundaries, refresh after removal, comments
inside argument lists, optional calls, executable template substitutions, module
scripts and Unicode in adjacent Python literals. The initial six cases failed
against the previous implementation and passed after the change.

Verification: all 455 local Windows tests passed; Ruff lint/format checks and
wheel/source builds passed. Native [CI run 34740903598](https://github.com/skanga/banger/actions/runs/34740903598)
at application commit `e5df6fb83ec0984458c5eb0c4816b64f6acc8a63` passed all six
Windows/Linux/macOS and Python 3.11/3.13 configurations, including tests, lint,
format and builds. This change was not separately exercised against a live model.

Limits at this checkpoint: receiver identity and execution are not established. Dynamic or escaped
selector values, bracket-based method access, event-handler attributes and legacy
script MIME aliases outside the recognized set are not resolved. External files
are workspace candidates rather than proof that a particular page loads them.
Escaped literals and literal bracket access are covered by the subsequent work above.

## HTML stylesheet applicability

Linked and embedded stylesheets with nontrivial `media` attributes no longer
contribute unconditional winners. Disabled links and alternate stylesheets are
also excluded, with explicit applicability/selection messages and source
locations. The `stylesheet` relationship is recognized within ASCII-whitespace
token lists and without case sensitivity. Missing/empty media and `all` retain
ordinary application. This follows the relevant
[HTML stylesheet rules](https://html.spec.whatwg.org/multipage/links.html#link-type-stylesheet)
and [media-attribute requirements](https://html.spec.whatwg.org/multipage/semantics.html#processing-the-media-attribute).

Thirteen cases in `test_stylesheet_applicability.py` cover linked/embedded media,
disabled boolean attributes, alternate selection, rel tokens, source locations
and refresh of Python-embedded markup. Twelve initial cases failed before the
fix; an additional embedded refresh case verifies switching from `print` to
`all`. Media-query evaluation, browser stylesheet-set selection and script-driven
activation remain unresolved. Reported computed values cover unconditional
rules alongside those explicit limitations.

Verification: all 446 local Windows tests passed, with Ruff lint/format checks
and wheel/source-distribution builds. Commit
`25151388f52aeb30e9b4a3762397d3b24887dff9` passed all six native Windows,
Linux and macOS jobs on Python 3.11 and 3.13, including tests, lint, formatting
and builds: [CI run 34740485260](https://github.com/skanga/banger/actions/runs/34740485260).

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
