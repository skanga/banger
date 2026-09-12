# Banger implementation and acceptance plan

Build independently; do not copy Benzi code, prompts, test fixtures, or assets.

## Milestones

1. Permission policy and persistent state: explicit mode selection, action approvals, mandatory escalation confirmation, workspace boundaries; SQLite conversations, memories, snapshots, index cache, and traces.
2. Language index: tree-sitter parsing for all ten code languages and markup; symbols, imports, references, ancestry, calls, unresolved/candidate evidence, incremental invalidation. Queries cover definitions, search, callers, call trees, paths, external calls, source outlines, and symbol profiles.
3. Editing and execution: atomic snapshots, syntax gates, semantic change reports, rollback with conflict detection, cmd/bash process lifecycle, cancellation, captured output, generated repros, Python runtime tracing and trace queries.
4. Analysis depth: call-site argument/return relationships, forward/backward flow, impact and relevant test selection; HTML/CSS/DOM-JS indexing, cascade and selector handling, embedded markup extraction.
5. Agent and models: Anthropic and OpenAI-compatible tool calling, local endpoint configuration, streaming, bounded retries, context management, persistent resumable history, explicit escalation approval.
6. TUI: setup and mode picker, chat, tool progress/output, source browser, diffs, session selection, interrupt/resume, mouse interaction. No graph or integrated editor required.
7. Acceptance: end-to-end coding tasks through both model adapters with deterministic fixtures; language-specific indexing and edit tests; markup and trace tests; persistence/recovery, permission bypass attempts, cancellation, and TUI interaction tests. Real provider smoke tests when credentials are available, without claiming mocked requests prove live compatibility.

## Verification scope

- Use meaningful failing behavior tests before each implementation unit.
- Cover every required language with real source fixtures and query expectations; a successful parse alone does not prove semantic support.
- Record static ambiguity rather than inventing resolved edges. Document runtime tracing language limits.
- Verify edits preserve existing work, reject invalid syntax, and restore snapshots across restarts.
- Cross-platform tests must run on Windows, Linux, and macOS before claiming cross-platform verification; local Windows checks alone are insufficient.
- Keep a feature/evidence checklist and report incomplete capabilities honestly. An initial working chat interface is not completion of the full goal.
- Container execution remains explicitly deferred to a later version.

## Library proposal

Textual supplies terminal widgets and headless UI interaction testing; tree-sitter-language-pack supplies native grammars; HTTPX supplies cancellable asynchronous HTTP; pytest supplies test orchestration. The user approved this dependency set; it is installed and locked in uv.lock.
