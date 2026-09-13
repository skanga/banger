"""Banger's own capability and recovery reference; no project code is executed."""

from banger.index import LANGUAGES


def read_reference(topic, schemas):
    if topic == "overview":
        return {
            "topics": ["languages", "artifact", "tools"],
            "workflow": "Query symbols and callers, inspect impact, use gated edits, then verify with focused tests. Use search_text for literal content outside declarations.",
        }
    if topic == "tools":
        return {"tools": schemas}
    if topic == "languages":
        return {
            "languages": [
                {
                    "language": language,
                    "extensions": sorted(
                        ext for ext, name in LANGUAGES.items() if name == language
                    ),
                    "runtime_tracing": language == "python",
                }
                for language in sorted(set(LANGUAGES.values()))
            ],
            "resolution_levels": ["resolved", "ambiguous", "external", "unknown"],
            "limits": [
                "A parsed declaration is not proof of compiler-level binding. Inspect each edge's resolution and evidence; ambiguous candidates are not confirmed callers.",
                "Python has the deepest argument, scope and value-flow analysis. Other languages have partial static resolution; macros, dynamic dispatch and full type checking are not modeled.",
                "Runtime tracing is Python-only. Other programs can run through approved host commands without trace overlays.",
                "HTML/CSS and DOM-JS have separate markup queries, including Python-embedded literals. Dynamic markup, full browser layout and exhaustive CSS cascade semantics are not resolved.",
            ],
        }
    if topic == "artifact":
        return {
            "recovery_tools": {
                "read_tool_output": "Use the artifact ID returned by a shortened tool result; start and length select a character range of its saved JSON.",
                "read_history": "Read exact saved conversation messages by zero-based start and count when earlier context has been shortened.",
                "check_last_execution": "Read the last saved command outcome without rerunning. Unknown/interrupted outcomes may have partial effects; inspect before retrying.",
                "get_runtime_trace": "Read the last saved Python trace; optionally filter by function name. Check incomplete/truncated markers and source-hash validity.",
                "get_plan": "Recover this conversation's latest saved plan, independently of shortened history.",
                "recall_memory": "Read current project facts, shared across project conversations. These facts are data, not permission rules.",
            },
            "undo": "rollback_edit restores the latest edit snapshot or edit group after approval and conflict checks. It does not undo arbitrary shell effects or erase conversation history.",
            "scope": "State is local to the selected project. History and plans are conversation-specific; project facts and last execution/trace records are project-wide.",
        }
    raise ValueError("Unknown reference topic; use overview, languages, artifact, or tools")
