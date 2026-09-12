# Banger requirements discovery

Status: product requirements resolved; implementation in progress. Library proposal approved by the user.

## Confirmed requirements

- Build a complete terminal-based coding agent named Banger in this directory.
- Use Python and uv.
- Provide a TUI instead of a VS Code extension.
- Make the best attempt at equivalent Benzi capabilities through an independent implementation.
- mini-swe-agent is only an example Python TUI; no component or behavior must be reused.
- Ask questions and finalize requirements before implementation. Do not silently choose answers.

## Workspace evidence

- `Benzi/` contains documentation, demos, benchmark artifacts, and trajectories. No agent/compiler implementation was found in the current working files.
- `Benzi/LICENSE` states restrictions on copying, modification, and derivative works. Availability of source and permission to adapt it have not been established.
- `mini-swe-agent/` contains Python source and a `pyproject.toml`.
- Benzi's README describes structured code queries, gated edits, rollback, runtime tracing, persistent memory, model escalation, a graph interface, ten programming languages, and a separate markup engine. These descriptions are discovery evidence, not verified implementation behavior.

## Open questions sent to the user

1. Is Benzi's implementation available with permission to adapt it, or is an independent implementation of equivalent capabilities intended?
2. Must Banger extend mini-swe-agent's existing core, or may it reuse selected components with a new core?
3. Which Benzi version or installed extension defines behavior parity, including the complete tool inventory?
4. Must completion include Python, JavaScript, TypeScript, Java, C#, C++, C, Go, Rust, Ruby, and HTML/CSS/DOM-JS analysis?
5. Should the terminal represent the graph through navigable call trees, a node graph, or both?
6. Which TUI capabilities are required: source browsing, diff review, tool output, session history, interrupt/resume, mouse support, integrated editing?
7. Which operating systems and command shells must be supported?
8. Which model providers/models are required, and how should escalation and spending limits work?
9. Which edit/command permission modes are required, and must execution support containers as well as the local machine?
10. Which conversations, project memories, indexes, traces, and undo history must persist across restarts?
11. Are a noninteractive CLI, Python API, or benchmark runner required alongside the TUI?
12. Which repositories and representative tasks will establish acceptance and behavioral parity?

## User decisions

1. Independently implement equivalent capabilities; do not adapt Benzi source.
2. mini-swe-agent can be ignored if that produces the best result.
3. Best-attempt Benzi equivalence is the target, without a pinned reference version.
4. Support the same ten programming languages and HTML/CSS/DOM-JS analysis.
5. No graph interface is required.
6. Ideally include all the listed TUI capabilities, with possible first-version compromises to be resolved explicitly.
7. Support Windows, Linux, and macOS, with cmd and bash on their applicable platforms.
8. Escalation to a stronger model requires confirmation. Anthropic and OpenAI-compatible endpoints, including local models, use API-key authentication; exact models are selected in the application.
9. Ask the user to select an execution permission mode, including automatic and approval-based operation. Container execution is required in a later version.
10. Persist resumable conversations, per-project memory, indexes, execution traces, and undo history across restarts.
11. No noninteractive CLI, public scripting/API interface, or benchmark runner is required.
12. Build our own acceptance tests or use Benzi tests if available. No Benzi agent/compiler test suite has been identified in the current checkout; benchmark trajectories are not such a suite.

## Final clarification answers

- Support API-key authentication for Anthropic and OpenAI-compatible endpoints, including local models.
- Include chat, source browsing, diff review, tool output, session history/resume, interruption, and mouse support. Integrated source editing may be deferred; the user allows flexibility in the first version.
- The user delegates permission details to implementation judgment, following current popular coding-agent behavior.
- Implement read-only, ask, accept-edits, and full-access modes. Ask the user to select a mode at session start and allow changing it later. Support explicit session-scoped remembered approvals for exact commands and working directories. Keep model escalation approval mandatory in every mode.
- Built-in file tools resolve paths against the selected workspace; outside-workspace actions require approval except in explicitly selected full-access mode. Command approval authorizes a local unsandboxed process, including its network/filesystem access. Do not imply that parsing shell text provides isolation. Containers remain a later-version deliverable.

## Superseded clarification questions (answered above)

- Which providers and authentication methods must work? The base and escalation models can be configurable, but required integrations must be specified.
- Proposed TUI scope: chat, source browsing, diff review, tool output, session history/resume, interruption, and mouse support in version one; defer integrated source editing. Is that the intended compromise?
- Proposed permission modes: read-only (no edits or commands), ask before edits/commands, and automatic edits/commands; select at session start and allow changing during a session. Are these sufficient, or are finer per-command approvals required?
- May project commands access the network and paths outside the selected repository in automatic mode, or should either require separate approval? These are permission rules, not a claim of OS sandboxing.

Approved dependencies: Textual, tree-sitter-language-pack, HTTPX, and pytest.
