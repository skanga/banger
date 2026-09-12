"""Match known bindings across edits without conflating same-named scopes."""

import re


def symbol_key(identity, index):
    symbol = index.symbols.get(identity)
    if symbol is None:
        return None
    names = [symbol["name"]]
    parent = symbol["parent"]
    while parent:
        owner = index.symbols[parent]
        names.append(owner["name"])
        parent = owner["parent"]
    return (
        symbol["path"],
        symbol.get("namespace", ""),
        symbol.get("cpp_scope", ""),
        tuple(reversed(names)),
    )


def call_key(call, index):
    return call["path"], call["name"], symbol_key(call["caller"], index)


def import_binding(call, index):
    file = index.files[call["path"]]
    name = re.split(r"\.|::|->", call["name"])[0]
    if file.get("language") != "python":
        return file.get("module_imports", {}).get(name)
    binding = file["imports"].get(name)
    for scope in reversed(index._visible_scopes(call)):
        binding = file.get("scoped_imports", {}).get(scope, {}).get(name, binding)
    return binding


def binding_regressions(before, after):
    known = {call_key(c, before): c for c in before.calls if c["resolution"] == "resolved"}
    regressions = []
    for call in after.calls:
        previous = known.get(call_key(call, after))
        if previous is None or call["resolution"] == "resolved":
            continue
        original_targets = {symbol_key(t, before) for t in previous["targets"]}
        remaining_targets = {symbol_key(t, after) for t in call["targets"]}
        if original_targets & remaining_targets:
            continue
        if call["resolution"] == "external" and import_binding(previous, before) != import_binding(
            call, after
        ):
            # An explicit import change is not a disappearance caused solely by
            # deleting an indexed module. Library availability is a runtime check.
            continue
        regressions.append(
            {
                **call,
                "binding_error": "Previously resolved project target is no longer available",
                "previous_targets": previous["targets"],
            }
        )
    return regressions
