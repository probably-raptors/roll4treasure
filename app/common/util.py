from typing import Dict
import json

def render_index(form_defaults: Dict, result: Dict | None = None) -> Dict[str, str]:
    return {
        "untapped_other_init": str(form_defaults.get("untapped_other_init", 0)),
        "stop_at_100": "checked" if form_defaults.get("stop_when_counters_ge_100", False) else "",
        "seed": "" if form_defaults.get("seed") is None else str(form_defaults["seed"]),
        "result_json": json.dumps(result) if result else "",
    }
