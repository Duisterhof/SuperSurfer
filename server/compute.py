"""Versioned project compute pools and read-only, bounded node inspection.

This module prepares placement contracts; AutoML alone chooses a host and
launches a reviewed run. Shell commands are always argv, never interpolated.
"""
from __future__ import annotations

import copy
import json
import math
from pathlib import PurePosixPath
import re
import subprocess
import sys
import time

from .aml import decoded


class ComputeError(ValueError):
    def __init__(self, message, status=400):
        super().__init__(message)
        self.status = status


DEFAULTS = {"python": None, "data_path": None, "storage_path": None}
CONTRACT_CAPABILITY = "placement.host_contracts.v1"
STAGING_CAPABILITY = "source.stage.v1"
SSH_OPTIONS = ["-T", "-o", "BatchMode=yes", "-o", "StrictHostKeyChecking=yes",
               "-o", "ClearAllForwardings=yes", "-o", "ForkAfterAuthentication=no",
               "-o", "PermitLocalCommand=no", "-o", "ConnectTimeout=8", "-o", "ConnectionAttempts=1"]


def _text(value, label, limit=4096):
    if not isinstance(value, str) or not value.strip() or len(value) > limit or any(ord(c) < 32 for c in value):
        raise ComputeError(f"{label} must be a nonempty string without control characters")
    return value.strip()


def _path(value, label, optional=False):
    if optional and (value is None or value == ""):
        return None
    value = _text(value, label)
    path = PurePosixPath(value)
    if not path.is_absolute() or ".." in path.parts:
        raise ComputeError(f"{label} must be an absolute path without '..'")
    return str(path)


def requirements(params, data_path):
    paths = params.get("required_paths", [])
    if not isinstance(paths, list) or len(paths) > 100:
        raise ComputeError("required_paths must list at most 100 paths")
    resolved = []
    for path in paths:
        path = _text(path, "required path")
        if "{data}" in path and not data_path:
            raise ComputeError("{data} requires a data_path")
        resolved.append(_path(path.replace("{data}", data_path or ""), "required path"))
    packages = params.get("python_packages", {})
    if not isinstance(packages, dict) or len(packages) > 100 or any(
        not isinstance(name, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,199}", name)
        or not isinstance(version, str) or not version.strip() or len(version) > 100 for name, version in packages.items()):
        raise ComputeError("python_packages must map distribution names to exact versions")
    return {"required_paths": list(dict.fromkeys(resolved)), "python_packages": dict(packages)}


def _integer(value, label, minimum=0, maximum=1024):
    if type(value) is not int or not minimum <= value <= maximum:
        raise ComputeError(f"{label} must be an integer between {minimum} and {maximum}")
    return value


def _gpu_indices(value, label):
    if not isinstance(value, list) or len(value) > 1024:
        raise ComputeError(f"{label} must be an array of device indices")
    indices = []
    for item in value:
        if isinstance(item, str) and re.fullmatch(r"[0-9]{1,4}", item):
            item = int(item)
        indices.append(_integer(item, label))
    if len(indices) != len(set(indices)):
        raise ComputeError(f"{label} cannot contain duplicate devices")
    return indices


class ComputePools:
    def __init__(self, store, aml):
        self.store, self.aml = store, aml

    def get(self, project_id):
        project_id = _text(project_id, "project_id", 150)
        return copy.deepcopy(self.store.get("compute_pool:" + project_id,
            {"project_id": project_id, "version": 0, "defaults": dict(DEFAULTS), "nodes": []}))

    def _snapshot(self, project_id=None):
        snapshot, error, _ = self.aml.status(force=True)
        if error:
            raise ComputeError("Cannot validate compute against AutoML: " + str(error), 503)
        if project_id is not None and not any(project.get("id") == project_id for project in snapshot.get("projects", [])):
            raise ComputeError("Project is not registered with AutoML", 404)
        return snapshot

    def _validate(self, project_id, params, current, snapshot):
        if not isinstance(params, dict) or set(params) - {"version", "defaults", "nodes"}:
            raise ComputeError("Compute settings accept only version, defaults and nodes")
        version = _integer(params.get("version"), "version", maximum=2**31 - 1)
        if version != current["version"]:
            raise ComputeError(f"Compute settings changed. Current version: {current['version']}. Reload before saving.", 409)
        defaults = dict(current["defaults"])
        if "defaults" in params:
            values = params["defaults"]
            if not isinstance(values, dict) or set(values) - set(DEFAULTS):
                raise ComputeError("Shared defaults accept only python, data_path and storage_path")
            defaults.update({key: _path(value, key, optional=True) for key, value in values.items()})
        nodes = params.get("nodes", current["nodes"])
        if not isinstance(nodes, list) or len(nodes) > 64:
            raise ComputeError("A project compute pool supports at most 64 nodes")
        hosts = {host["id"]: host for host in snapshot.get("hosts", [])}
        seen, checked = set(), []
        for node in nodes:
            if not isinstance(node, dict) or set(node) - {"host_id", "enabled", "repo_path", *DEFAULTS, "gpu_indices"}:
                raise ComputeError("Invalid compute node fields")
            host_id = _text(node.get("host_id"), "host_id", 150)
            if host_id not in hosts:
                raise ComputeError("Compute node is not a registered host: " + host_id)
            if host_id in seen:
                raise ComputeError("Compute nodes must use distinct host IDs")
            seen.add(host_id)
            enabled = node.get("enabled", True)
            if type(enabled) is not bool:
                raise ComputeError("Node enabled must be a boolean")
            record = {"host_id": host_id, "enabled": enabled,
                      "repo_path": _path(node.get("repo_path"), "repo_path", optional=not enabled)}
            for key in DEFAULTS:
                if key in node:
                    record[key] = _path(node[key], key, optional=True)
                if enabled and not (record.get(key) or defaults[key]):
                    raise ComputeError(f"Node {host_id} needs {key} or a shared default")
            if node.get("gpu_indices") is not None:
                allowed = _gpu_indices(node["gpu_indices"], "gpu_indices")
                registered = _gpu_indices(decoded(hosts[host_id].get("gpus"), []), "Registered GPUs")
                if not set(allowed) <= set(registered):
                    raise ComputeError(f"GPU subset for {host_id} contains an unregistered device")
                record["gpu_indices"] = allowed
            checked.append(record)
        return {"project_id": project_id, "version": version + 1, "defaults": defaults,
                "nodes": checked, "updated_at": time.time()}

    def save(self, project_id, params):
        project_id = _text(project_id, "project_id", 150)
        with self.store.lock:
            current = self.get(project_id)
            snapshot = self._snapshot(project_id)
            value = self._validate(project_id, params, current, snapshot)
            previous = {node["host_id"]: node for node in current["nodes"]}
            applied = []
            for node in value["nodes"]:
                old = previous.get(node["host_id"], {})
                if not node["enabled"] or (old.get("enabled") and old.get("repo_path") == node["repo_path"]):
                    continue
                try:
                    self.aml.call("host.repo", {"host": node["host_id"], "project": project_id, "path": node["repo_path"]})
                    applied.append(node["host_id"])
                except Exception as exc:
                    self.aml.invalidate()
                    detail = " Repository mappings already updated: " + ", ".join(applied) + "." if applied else ""
                    raise ComputeError("Compute settings were not saved because a repository mapping failed: " + str(exc) + detail + " Reload and retry the settings; no run was submitted.", 503) from exc
            self.store.put("compute_pool:" + project_id, value)
            self.aml.invalidate()
            return copy.deepcopy(value)

    def onboard_node(self, project_id, params):
        """Validate and merge one node, preserving every unrelated pool setting."""
        if not isinstance(params, dict) or set(params) - {"version", "node", "required_paths", "python_packages"}:
            raise ComputeError("Onboarding accepts version, node and optional input requirements")
        current = self.get(project_id)
        node = params.get("node")
        if not isinstance(node, dict) or node.get("enabled", True) is not True:
            raise ComputeError("Onboarding requires one enabled node")
        nodes = [node if row["host_id"] == node.get("host_id") else row for row in current["nodes"]]
        if not any(row["host_id"] == node.get("host_id") for row in current["nodes"]):
            nodes.append(node)
        planned = self._validate(project_id, {"version": params.get("version"), "nodes": nodes}, current, self._snapshot(project_id))
        node = next(row for row in planned["nodes"] if row["host_id"] == node["host_id"])
        hints = {key: node.get(key) or planned["defaults"][key] for key in DEFAULTS}
        inspection = self.inspect_host({"host_id": node["host_id"], "repo_path": node["repo_path"], **hints,
            **{key: params[key] for key in ("required_paths", "python_packages") if key in params}}, verify_runtime=True)
        if not inspection.get("ready"):
            raise ComputeError("Node setup is incomplete: " + "; ".join(inspection.get("blockers", ["inspection did not confirm readiness"])), 409)
        # Compare-and-swap after the network probe; concurrent edits must not be lost.
        saved = self.save(project_id, {"version": current["version"], "nodes": planned["nodes"]})
        return {"pool": saved, "inspection": inspection, "host_id": node["host_id"], "ready": True,
                "note": "Configured for future run submissions; existing queued contracts are unchanged."}

    def resolve_run(self, project_id, params, project, pool=None):
        """Return pool contract pieces, leaving actual placement to AutoML."""
        project_id = _text(project_id, "project_id", 150)
        if not isinstance(params, dict) or not isinstance(project, dict) or project.get("id") != project_id:
            raise ComputeError("Run project does not match its compute pool")
        snapshot = self._snapshot(project_id)
        try:
            capabilities = self.aml.call("ping").get("capabilities", [])
        except Exception as exc:
            raise ComputeError("Cannot verify AutoML compute-pool support: " + str(exc), 503) from exc
        if not isinstance(capabilities, list) or not all(isinstance(item, str) for item in capabilities) or not {CONTRACT_CAPABILITY, STAGING_CAPABILITY} <= set(capabilities):
            raise ComputeError("This AutoML manager does not support project compute pools with reviewed source staging. Update AutoML before submitting a pooled run.", 409)
        pool = self.get(project_id) if pool is None else pool
        # Revalidate saved masks against today's registered resources.
        self._validate(project_id, {"version": pool["version"]}, pool, snapshot)
        command = params.get("command")
        if not isinstance(command, list) or not 1 <= len(command) <= 1000 or any(not isinstance(arg, str) or len(arg) > 32000 or "\0" in arg for arg in command) or not command[0]:
            raise ComputeError("Command must be a nonempty argv array")
        count = _integer(params.get("gpu_count"), "gpu_count")
        if count > project.get("gpu_limit", 1024):
            raise ComputeError("GPU request exceeds the project's limit")
        storage = params.get("storage_gib")
        if type(storage) not in (int, float) or not math.isfinite(storage) or storage < 0:
            raise ComputeError("storage_gib must be a nonnegative finite number")
        revision = params.get("revision")
        if not isinstance(revision, str) or not re.fullmatch(r"[0-9a-fA-F]{40}", revision):
            raise ComputeError("A pooled run needs its exact full 40-character Git commit revision")
        source = _path(params.get("repo") or project.get("repo"), "Source repository")
        overrides = {key: _path(params.get(key), key, optional=True) for key in DEFAULTS}
        hosts = {host["id"]: host for host in snapshot.get("hosts", [])}
        contracts, excluded = {}, {}
        for node in pool["nodes"]:
            if not node["enabled"]:
                continue
            host_id = node["host_id"]
            mask = node.get("gpu_indices", _gpu_indices(decoded(hosts[host_id].get("gpus"), []), "Registered GPUs"))
            if len(mask) < count:
                excluded[host_id] = "Fewer allowed GPUs than requested"
                continue
            resolved = {key: overrides[key] or node.get(key) or pool["defaults"][key] for key in DEFAULTS}
            argv = [arg.replace("{python}", resolved["python"]).replace("{data}", resolved["data_path"]) for arg in command]
            if argv[0] == "python":
                argv[0] = resolved["python"]
            needed = requirements(params, resolved["data_path"])
            environment = {"python": resolved["python"], "executables": [argv[0]],
                           "paths": list(dict.fromkeys([resolved["data_path"], *needed["required_paths"]]))}
            if needed["python_packages"]:
                environment["packages"] = needed["python_packages"]
            contracts[host_id] = {"command": argv,
                "environment": environment,
                "storage": {"directory": resolved["storage_path"], "min_free_gib": storage},
                "env": {"SUPERSURFER_DATA_PATH": resolved["data_path"]},
                "allowed_gpu_indices": [str(index) for index in mask]}
        if not contracts:
            raise ComputeError("No enabled project node can satisfy the requested GPU count. Configure the compute pool or reduce the request.", 409)
        allowed = list(contracts)
        return {"allowed_hosts": allowed, "host_contracts": contracts,
                # Required by legacy AML storage only; never a placement choice.
                "preferred_host": allowed[0], "source_repo": source, "revision": revision.lower(),
                "pool_snapshot": copy.deepcopy(pool), "excluded_hosts": excluded,
                "stage_source_supported": STAGING_CAPABILITY in capabilities}

    def inspect_host(self, params, verify_runtime=False):
        if not isinstance(params, dict) or set(params) - {"host_id", "target", "repo_path", "required_paths", "python_packages", *DEFAULTS}:
            raise ComputeError("Host inspection accepts a registered host ID or SSH target and optional path hints")
        if "host_id" in params and "target" in params:
            raise ComputeError("Specify either host_id or target")
        host = None
        if "host_id" in params:
            host_id = _text(params["host_id"], "host_id", 150)
            host = next((row for row in self._snapshot().get("hosts", []) if row["id"] == host_id), None)
            if host is None:
                raise ComputeError("Host is not registered", 404)
            target = host.get("target")
        else:
            target = _text(params["target"], "SSH target", 255) if params.get("target") != "" and "target" in params else None
        if target and (not re.fullmatch(r"[A-Za-z0-9_.@:%+\[\]-]+", target) or target.startswith("-")):
            raise ComputeError("Invalid SSH target; use a hostname, SSH alias or user@host")
        hints = {key: _path(params.get(key), key, optional=True) for key in ("repo_path", *DEFAULTS)}
        hints.update(requirements(params, hints["data_path"]))
        hints["verify_runtime"] = verify_runtime or bool(hints["python_packages"])
        script = _PROBE + "\nprobe(json.loads(" + repr(json.dumps(hints)) + "))\n"
        command = ["ssh", *SSH_OPTIONS, "--", target, "python3 -"] if target else [sys.executable, "-"]
        try:
            result = subprocess.run(command, input=script, text=True, capture_output=True, timeout=20, check=False)
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise ComputeError("Read-only host inspection failed: " + str(exc), 503) from exc
        if result.returncode or len(result.stdout) > 256000:
            raise ComputeError("Read-only host inspection failed: " + (result.stderr.strip()[-2000:] or "No bounded probe response"), 503)
        try:
            marked = [line.removeprefix("SUPERSURFER_PROBE:") for line in result.stdout.splitlines() if line.startswith("SUPERSURFER_PROBE:")]
            value = json.loads(marked[-1] if marked else result.stdout)
            if not isinstance(value, dict) or not isinstance(value.get("gpus"), list) or not isinstance(value.get("paths"), dict):
                raise ValueError("Unexpected probe response")
        except ValueError as exc:
            raise ComputeError("The host did not return a valid inspection response", 503) from exc
        return {**value, "host_id": host["id"] if host else None, "target": target,
                "registered_gpu_indices": _gpu_indices(decoded(host.get("gpus"), []), "Registered GPUs") if host else None,
                "observed_at": time.time()}


_PROBE = r'''
import csv, json, os, pathlib, shutil, subprocess, sys
def probe(hints):
    paths = {}
    for key in ("repo_path", "python", "data_path", "storage_path"):
        value=hints.get(key)
        if value:
            path = pathlib.Path(value)
            paths[key] = {"path":value,"exists":path.exists(),"is_directory":path.is_dir(),"is_executable":path.is_file() and os.access(path,os.X_OK),"writable":os.access(path,os.W_OK)}
            if path.is_dir():
                paths[key]["free_gib"] = round(shutil.disk_usage(path).free / 2**30, 2)
    def existing(values, executable=False):
        result=[]
        for value in values:
            if value and value not in result and (pathlib.Path(value).is_file() and os.access(value,os.X_OK) if executable else pathlib.Path(value).is_dir()): result.append(value)
        return result[:12]
    repo=hints.get("repo_path")
    home=pathlib.Path.home()
    suggestions={"python":existing([shutil.which("python3"),shutil.which("python"),str(pathlib.Path(repo)/".venv/bin/python") if repo else None],True),"data_path":existing([hints.get("data_path"),str(home/"data"),str(home/"datasets"),"/data","/datasets"]),"storage_path":existing([hints.get("storage_path"),"/scratch","/data",str(home)])}
    blockers=[]; checks={}
    for key in ("repo_path", "python", "data_path", "storage_path"):
        if not hints.get(key):
            blockers.append("Missing " + key)
        elif not paths[key]["exists"]:
            blockers.append("Missing " + key + ": " + hints[key])
    for key in ("repo_path", "data_path", "storage_path"):
        if hints.get(key) and not paths[key]["is_directory"]:
            blockers.append(key + " must be a directory")
    if hints.get("storage_path") and not paths["storage_path"]["writable"]:
        blockers.append("Storage is not writable")
    if repo and paths["repo_path"]["is_directory"]:
        try:
            bare=subprocess.run(["git","-C",repo,"rev-parse","--is-bare-repository"],stdout=subprocess.PIPE,stderr=subprocess.PIPE,universal_newlines=True,timeout=3)
            is_bare=bare.returncode==0 and bare.stdout.strip()=="true"
            result=subprocess.run(["git","-C",repo,"rev-parse","--absolute-git-dir" if is_bare else "--show-toplevel"],stdout=subprocess.PIPE,stderr=subprocess.PIPE,universal_newlines=True,timeout=3)
            checks["repository"]={"ok":result.returncode==0 and pathlib.Path(result.stdout.strip()).resolve()==pathlib.Path(repo).resolve(),"bare":is_bare}
            if not checks["repository"]["ok"]:blockers.append("Repository path is not a Git repository root")
        except (OSError, subprocess.TimeoutExpired):blockers.append("Repository could not be checked")
    interpreter=hints.get("python")
    if interpreter and paths["python"]["is_executable"] and hints["verify_runtime"]:
        try:
            code="import json,sys; packages=json.loads(sys.argv[1]); versions={}; "
            if hints["python_packages"]:
                code+="import importlib.metadata as m; versions={name:m.version(name) for name in packages}; "
            code+="print(json.dumps({'version':list(sys.version_info[:3]),'packages':versions}))"
            result=subprocess.run([interpreter,"-c",code,json.dumps(hints["python_packages"])],stdout=subprocess.PIPE,stderr=subprocess.PIPE,universal_newlines=True,timeout=4)
            if result.returncode:raise ValueError("Interpreter or required distributions unavailable")
            checks["python"]=json.loads(result.stdout)
            for name,version in hints["python_packages"].items():
                if checks["python"]["packages"].get(name)!=version:blockers.append("Python distribution version mismatch: "+name)
        except (OSError,ValueError,subprocess.TimeoutExpired):blockers.append("Python or required distributions could not be verified")
    elif interpreter and not paths["python"]["is_executable"]:blockers.append("Python is not executable")
    checks["required_paths"]=[{"path":value,"exists":pathlib.Path(value).exists()} for value in hints["required_paths"]]
    blockers.extend("Missing required input: "+item["path"] for item in checks["required_paths"] if not item["exists"])
    gpus=[];error=None
    try:
        result=subprocess.run(["nvidia-smi","--query-gpu=index,name,memory.total,memory.free,utilization.gpu","--format=csv,noheader,nounits"],stdout=subprocess.PIPE,stderr=subprocess.PIPE,universal_newlines=True,timeout=6)
        if result.returncode:error="nvidia-smi could not read GPU status"
        else:
            for row in list(csv.reader(result.stdout.splitlines()))[:64]:
                if len(row)!=5:continue
                try:gpus.append({"index":int(row[0]),"name":row[1].strip()[:200],"memory_total_mib":int(row[2]),"memory_free_mib":int(row[3]),"utilization":int(row[4])})
                except ValueError:continue
    except (OSError,subprocess.TimeoutExpired):error="GPU inspection unavailable: nvidia-smi is missing or timed out"
    print("SUPERSURFER_PROBE:" + json.dumps({"ready":not blockers if hints["verify_runtime"] else False,"runtime_verified":hints["verify_runtime"] and "python" in checks,"blockers":blockers,"checks":checks,"gpus":gpus,"gpu_error":error,"paths":paths,"suggestions":suggestions,"inspection_python":{"path":sys.executable,"version":list(sys.version_info[:3]),"compatible":sys.version_info >= (3,9),"note":"Inspection interpreter only. The runner requires Python 3.9+; registration can use auto to discover a compatible interpreter. Project Python is independent."},"read_only":True,"availability_note":"GPU measurements are observations; scheduler reservations determine run eligibility."}))
'''
