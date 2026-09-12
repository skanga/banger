"""Candidate narrowing for ordinary Python instance-method receivers."""


class ReceiverBindings:
    def __init__(self, index):
        self.index = index
        self.families = {}

    def resolve(self, call, candidates):
        owner = self.index.symbols.get(call["caller"], {})
        receiver = owner.get("implicit_receiver")
        parts = call["name"].split(".")
        if (
            not receiver
            or len(parts) != 2
            or parts[0] != receiver
            or receiver in owner.get("bindings", [])
        ):
            return None
        identity = owner["parent"]
        if identity not in self.families:
            descendants, pending = set(), [identity]
            while pending:
                current = pending.pop()
                if current in descendants:
                    continue
                descendants.add(current)
                hierarchy = self.index.hierarchies[current]
                pending.extend(s["id"] for s in hierarchy["subclasses"])
                pending.extend(s["symbol"]["id"] for s in hierarchy["candidate_subclasses"])
            family, pending = set(), list(descendants)
            while pending:
                current = pending.pop()
                if current in family:
                    continue
                family.add(current)
                for link in self.index.hierarchies[current]["base_links"]:
                    pending.extend(link["targets"])
            self.families[identity] = family
        targets = [s["id"] for s in candidates if s["parent"] in self.families[identity]]
        return {
            "targets": targets,
            "resolution": "ambiguous" if targets else "unknown",
            "evidence": "implicit receiver hierarchy candidates; overrides, rebinding and dynamic attributes require runtime evidence",
        }
