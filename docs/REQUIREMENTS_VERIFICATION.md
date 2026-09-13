# Requirements verification handoff

The governing scope is the user's finalized decisions in `REQUIREMENTS.md`:
an independent Python/uv terminal coding agent making the best attempt at the
documented Benzi capabilities. This is not a claim of exact equivalence to an
unavailable proprietary compiler. Graph UI is excluded; integrated source editing
and containers are deferred. The requirements are not reopened by this audit.

## Current artifacts

- Application source: `74999027c6318649d34699820349f5687621b27a`.
- Local verification: 623 tests passed, two POSIX-only skips; lint, formatting,
  wheel and source-distribution builds passed.
- Installed Windows wheel SHA-256:
  `82adfd73dfe1b680333e702a5fa077b57bae91b713635c3e36fe9b5cc3f8e0a7`.
  Installed Python modules were compared byte-for-byte with current source.
- A live task using the user-selected local OpenAI-compatible model verified
  planning, reference/dependency tools, regex search, approved editing/execution,
  Python tracing and exact conversation/plan recovery. Its rendered TUI capture
  was inspected locally. Raw history/captures remain local.
- The prior source passed six native jobs in
  [run 34749073583](https://github.com/skanga/banger/actions/runs/34749073583).
  That run includes dependency listing and the corrected process-lifecycle test.
  It does not include the subsequent search-preview/column change.

## Requirement-to-evidence mapping

| Agreed requirement | Implementation and inspected evidence | Verification boundary |
|---|---|---|
| Python, uv, terminal application | `pyproject.toml` launcher/dependencies; `app.py`; built and installed wheel | Windows installed-wheel live check; native build evidence for prior source |
| Independent implementation; example TUI optional | Banger's own modules, prompts and tests; reference docs/tool names used for discovery | No proprietary source comparison or benchmark-score parity claim |
| Ten code languages and markup | `index.py`, bindings/hierarchy modules, `markup.py`; `test_language_edits.py` exercises queries, rejected syntax/lost bindings, edits, impact and restart undo for all ten | Grammar parsing plus supported static bindings; no exhaustive compiler semantics claim |
| Structured queries and value flow | Definitions, callers, closure/paths, hierarchy, references, outlines, profile and flow tools; language/flow regression suites | Python is deepest; dynamic dispatch, macros, complex module/type systems retain documented limits |
| HTML/CSS/DOM-JS and embedded markup | Markup, stylesheet, DOM and embedded-source-map tests | Static selectors/cascade and source provenance; dynamic/browser-dependent behavior remains limited |
| Gated writes, impact, verification and rollback | `Editor`, tools, state; single/grouped edit, semantic-gate and undo-recovery tests | Shell side effects are not edit snapshots; grouped edits are not filesystem-wide atomic |
| Local execution and runtime tracing | `Executor`, trace runner, generated-testcase tools; execution/trace tests and live task | Python runtime tracing; cmd/bash execution for other programs; host execution is unsandboxed |
| Durable history, facts, indexes, traces and undo | SQLite state, restart/recovery tests, context artifacts; live reopened conversation | Shortened model context is an excerpt; exact history remains recoverable on disk |
| Familiar coding-agent utilities | Literal/regex search, declared dependencies, reference help, session plans, save/forget facts | Search/worker limits explicit; dependency declarations do not imply installed/resolved packages |
| Anthropic and OpenAI-compatible/local endpoints | `models.py`; both provider protocols in mocked end-to-end tasks; streaming/auth/error tests; live local endpoint | No live Anthropic credentials supplied; mocked evidence is not labeled live |
| Mandatory stronger-model confirmation | Agent escalation and permission-policy tests | No automatic bypass in any permission mode |
| Selectable execution/edit modes | Explicit setup selection, mode picker, permission tests, live ask/read-only tasks | Exact command/cwd remembered approvals; source-data text cannot change policy |
| Chat, source, diff, tools, sessions, interrupt and mouse | TUI/end-to-end/wrapping tests; live driver capture; native console/PTY checks | Emulator-specific pixel rendering is not exhaustively tested |
| Windows, Linux and macOS; applicable cmd/bash shells | Six-job native matrix; Windows console and POSIX PTY tests | Latest search-preview change still requires native verification |
| No graph, no public headless API/benchmark requirement | Interactive launcher and agreed exclusions retained | Containers and integrated editing remain deferred, not silently claimed complete |

## Outstanding verification

The latest native run,
[34749223405](https://github.com/skanga/banger/actions/runs/34749223405),
was refused during runner allocation before tests started. The repository has
zero configured self-hosted runners. Attempt 3 also completed with all six jobs
refused before tests started; hosted runner availability has not been restored.
A successful native result for the latest
source, or another authorized native runner, is still required; earlier green
jobs and local Windows results do not prove this final check.

Known analysis limits remain documented in `README.md` and `FEATURE_AUDIT.md`.
They are not erased by the test count or this handoff. Completion remains
unproven until the outstanding verification is resolved and the evidence is
reviewed against this mapping.
