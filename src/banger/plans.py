"""Validated session plans, stored independently from shortened tool history."""

import json


def validate_plan(plan_json, explanation):
    steps = json.loads(plan_json)
    if not isinstance(steps, list) or len(steps) > 20:
        raise ValueError("A plan must be a JSON list of at most 20 steps")
    if len(explanation) > 2000:
        raise ValueError("Plan explanation must be at most 2000 characters")
    for item in steps:
        if (
            not isinstance(item, dict)
            or set(item) != {"step", "status"}
            or not isinstance(item["step"], str)
            or not item["step"].strip()
            or len(item["step"]) > 500
            or item["status"] not in ("pending", "in_progress", "completed")
        ):
            raise ValueError(
                "Each step needs text (1-500 characters) and status pending, in_progress, or completed"
            )
    if sum(item["status"] == "in_progress" for item in steps) > 1:
        raise ValueError("At most one plan step may be in_progress")
    return {"steps": steps, "explanation": explanation}
