"""Diff logic — compare two version snapshots and produce human-readable changes."""
from __future__ import annotations

import json
from typing import Any, TYPE_CHECKING

from eurekalab.versioning.snapshot import BusSnapshot

if TYPE_CHECKING:
    from eurekalab.versioning.store import VersionStore


def diff_versions(store: VersionStore, v1_num: int, v2_num: int) -> list[str]:
    """Compare two versions and return a list of human-readable change descriptions."""
    ver1 = store.get(v1_num)
    ver2 = store.get(v2_num)
    if ver1 is None or ver2 is None:
        raise ValueError(f"Version not found: v{v1_num} or v{v2_num}")
    snap1 = BusSnapshot.from_json(ver1.snapshot_json)
    snap2 = BusSnapshot.from_json(ver2.snapshot_json)
    return _diff_snapshots(snap1, snap2)


def _diff_snapshots(old: BusSnapshot, new: BusSnapshot) -> list[str]:
    changes: list[str] = []
    all_keys = set(old.artifacts.keys()) | set(new.artifacts.keys())
    for key in sorted(all_keys):
        old_raw = old.artifacts.get(key)
        new_raw = new.artifacts.get(key)
        if old_raw is None and new_raw is not None:
            changes.append(f"Added: {key}")
            continue
        if old_raw is not None and new_raw is None:
            changes.append(f"Removed: {key}")
            continue
        if old_raw == new_raw:
            continue
        old_data = json.loads(old_raw)
        new_data = json.loads(new_raw)
        key_changes = _diff_artifact(key, old_data, new_data)
        changes.extend(key_changes)
    return changes


def _diff_artifact(key: str, old: Any, new: Any) -> list[str]:
    if key == "bibliography":
        return _diff_bibliography(old, new)
    if key == "research_brief":
        return _diff_brief(old, new)
    if key == "theory_state":
        return _diff_theory(old, new)
    if old != new:
        return [f"Modified: {key}"]
    return []


def _diff_bibliography(old: dict, new: dict) -> list[str]:
    changes: list[str] = []
    old_ids = {p["paper_id"] for p in old.get("papers", [])}
    new_papers = new.get("papers", [])
    new_ids = {p["paper_id"] for p in new_papers}
    added = new_ids - old_ids
    removed = old_ids - new_ids
    if added:
        titles = {p["paper_id"]: p.get("title", "?") for p in new_papers}
        for pid in sorted(added):
            changes.append(f"Bibliography: +paper '{titles.get(pid, pid)}' ({pid})")
    if removed:
        changes.append(f"Bibliography: -{len(removed)} paper(s) removed")
    return changes


def _diff_brief(old: dict, new: dict) -> list[str]:
    changes: list[str] = []
    for field in ("domain", "query", "conjecture"):
        ov = old.get(field, "")
        nv = new.get(field, "")
        if ov != nv and nv:
            changes.append(f"Brief: {field} changed to '{nv}'")
    old_dirs = {d.get("title", "") for d in old.get("directions", [])}
    new_dirs = {d.get("title", "") for d in new.get("directions", [])}
    for title in sorted(new_dirs - old_dirs):
        if title:
            changes.append(f"Brief: +direction '{title}'")
    for title in sorted(old_dirs - new_dirs):
        if title:
            changes.append(f"Brief: -direction '{title}'")
    # injected_ideas — currently simple strings, will become InjectedIdea objects in Phase 5
    old_ideas = set(old.get("injected_ideas", []))
    new_ideas = set(new.get("injected_ideas", []))
    for idea in sorted(new_ideas - old_ideas):
        changes.append(f"Brief: +injected idea '{idea[:60]}'")
    return changes


def _diff_theory(old: dict, new: dict) -> list[str]:
    changes: list[str] = []
    # proven_lemmas is dict[str, ProofRecord] — keys are lemma IDs
    old_proven = set(old.get("proven_lemmas", {}).keys())
    new_proven_dict = new.get("proven_lemmas", {})
    new_proven = set(new_proven_dict.keys())
    added = new_proven - old_proven
    if added:
        for lid in sorted(added):
            record = new_proven_dict.get(lid, {})
            proof_text = record.get("proof_text", "")[:60]
            changes.append(f"Theory: +proven lemma {lid} '{proof_text}'")
    old_status = old.get("status", "")
    new_status = new.get("status", "")
    if old_status != new_status:
        changes.append(f"Theory: status {old_status} -> {new_status}")
    return changes
