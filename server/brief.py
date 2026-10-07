"""A bounded current experiment brief; activity and technical notes stay separate."""
import time
from .store import Conflict


LIMITS = {"objective": 1500, "method": 3500, "findings": 3500, "next_steps": 1500}


def read(store, experiment_id):
    experiment = store.experiment(experiment_id)
    return store.get("brief:" + experiment_id, {"version": 0, "objective": experiment.get("summary", "")[:1500],
        "method": "", "findings": "", "next_steps": "", "activity": [], "updated": None})


def update(store, experiment_id, fields):
    if not isinstance(fields, dict) or set(fields) - {*LIMITS, "version", "activity"}:
        raise ValueError("Brief accepts version, objective, method, findings, next_steps and activity")
    if type(fields.get("version")) is not int:
        raise ValueError("Read the current brief and supply its version")
    if not set(fields) & {*LIMITS, "activity"}:
        raise ValueError("Provide a section update or activity note")
    for key, limit in {**LIMITS, "activity": 1000}.items():
        if key in fields and (not isinstance(fields[key], str) or len(fields[key]) > limit or "\0" in fields[key]):
            raise ValueError(f"Brief {key} must be text up to {limit} characters; detailed evidence belongs in Results or technical notes")
    with store.lock:
        current = read(store, experiment_id)
        if fields["version"] != current["version"]:
            raise Conflict("Brief changed. Read its current version and reconcile before saving.")
        now = time.time()
        for key in LIMITS:
            if key in fields:
                current[key] = fields[key].strip()
        note = fields.get("activity", "").strip()
        if note and (not current["activity"] or current["activity"][-1]["text"] != note):
            current["activity"] = (current["activity"] + [{"at": now, "text": note}])[-100:]
        current.update(version=current["version"] + 1, updated=now)
        store.put("brief:" + experiment_id, current)
        return current
