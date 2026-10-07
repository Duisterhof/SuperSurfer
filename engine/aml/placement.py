"""Explicit contracts for selecting a registered host and staging input files."""
from __future__ import annotations

import copy
import json
import math
from pathlib import PurePosixPath
import re


def absolute_path(value, label):
    if not isinstance(value, str) or not value.startswith("/") or "\x00" in value:
        raise ValueError(f"{label} must be an absolute path")
    if ".." in PurePosixPath(value).parts:
        raise ValueError(f"{label} cannot contain '..'")
    return value


def normalize_contract(store, preferred, command, config, allowed_hosts=None, environment=None,
                       storage=None, inputs=None):
    config = dict(config or {})
    requested = allowed_hosts if allowed_hosts is not None else config.get("allowed_hosts")
    contract_environment = environment if environment is not None else config.get("environment")
    contract_storage = storage if storage is not None else config.get("storage")
    contract_inputs = inputs if inputs is not None else config.get("inputs")
    host_contracts = config.get("host_contracts")
    if "host_contracts" in config and not isinstance(host_contracts, dict):
        raise ValueError("host_contracts must map canonical host IDs to contracts")
    stage_source = config.get("stage_source", False)
    if type(stage_source) is not bool:
        raise ValueError("stage_source must be boolean")
    if stage_source and host_contracts is None:
        raise ValueError("Source staging requires explicit host_contracts")
    if all(value is None for value in (requested, contract_environment, contract_storage, contract_inputs, host_contracts)):
        return config
    if requested is None:
        requested = [preferred["id"]]
    if not isinstance(requested, list) or not requested:
        raise ValueError("allowed_hosts must be a nonempty list of registered host names or IDs")
    hosts = [store.get("hosts", host) for host in requested]
    host_ids = [host["id"] for host in hosts]
    if len(set(host_ids)) != len(host_ids) or preferred["id"] not in host_ids:
        raise ValueError("allowed_hosts must be unique and include the preferred --host")
    contract_environment = contract_environment or {}
    if not isinstance(contract_environment, dict) or set(contract_environment) - {"executables", "paths", "python", "packages"}:
        raise ValueError("environment accepts only executables, paths, python and packages")
    executables = contract_environment.get("executables", [command[0]])
    paths = contract_environment.get("paths", [])
    if not isinstance(executables, list) or not executables or any(not isinstance(item, str) or not item for item in executables):
        raise ValueError("environment.executables must be a nonempty list of executable paths or names")
    if not isinstance(paths, list):
        raise ValueError("environment.paths must be a list")
    paths = [absolute_path(item, "Required environment path") for item in paths]
    interpreter = contract_environment.get("python")
    packages = contract_environment.get("packages", {})
    if interpreter is not None:
        interpreter = absolute_path(interpreter, "Python interpreter")
    if not isinstance(packages, dict) or any(not isinstance(key, str) or not key or
                                             not isinstance(value, str) or not value for key, value in packages.items()):
        raise ValueError("environment.packages must map distribution names to exact version strings")
    if packages and interpreter is None:
        raise ValueError("environment.packages requires an explicit absolute Python interpreter")
    if contract_storage is not None:
        if not isinstance(contract_storage, dict) or set(contract_storage) - {"directory", "min_free_gib"}:
            raise ValueError("storage accepts only directory and min_free_gib")
        directory = absolute_path(contract_storage.get("directory"), "Storage directory")
        minimum = contract_storage.get("min_free_gib", 0)
        if not isinstance(minimum, (int, float)) or isinstance(minimum, bool) or not math.isfinite(minimum) or minimum < 0:
            raise ValueError("storage.min_free_gib must be a nonnegative number")
        contract_storage = {"directory": directory, "min_free_gib": minimum}
    contract_inputs = contract_inputs or []
    if not isinstance(contract_inputs, list):
        raise ValueError("inputs must be a list of explicit file transfers")
    if contract_inputs and contract_storage is None:
        raise ValueError("Input staging requires an explicit storage directory")
    normalized_inputs = []
    destinations = set()
    for item in contract_inputs:
        if not isinstance(item, dict) or set(item) - {"source", "source_host", "destination", "sha256", "size_bytes"}:
            raise ValueError("Each input accepts source, source_host, destination, sha256 and size_bytes")
        source = absolute_path(item.get("source"), "Input source")
        destination = absolute_path(item.get("destination"), "Input destination")
        if not PurePosixPath(destination).is_relative_to(PurePosixPath(contract_storage["directory"])):
            raise ValueError("Input destination must be inside the declared storage directory")
        if destination == contract_storage["directory"] or destination in destinations:
            raise ValueError("Input destinations must be unique files inside the storage directory")
        destinations.add(destination)
        digest = item.get("sha256", "")
        if not isinstance(digest, str) or not re.fullmatch(r"[0-9a-fA-F]{64}", digest):
            raise ValueError("Every input requires its expected SHA-256")
        size = item.get("size_bytes")
        if not isinstance(size, int) or isinstance(size, bool) or size < 0:
            raise ValueError("Every input requires its exact nonnegative size_bytes")
        source_host = item.get("source_host")
        if source_host == "manager":
            source_host = None
        if source_host is not None:
            source_host = store.get("hosts", source_host)["id"]
        normalized_inputs.append({"source": source, "source_host": source_host, "destination": destination,
                                  "sha256": digest.lower(), "size_bytes": size})
    normalized_environment = {"executables": executables, "paths": paths}
    if interpreter is not None:
        normalized_environment.update(python=interpreter, packages=packages)
    config.update(allowed_hosts=host_ids, environment=normalized_environment, inputs=normalized_inputs)
    if contract_storage is not None:
        config["storage"] = contract_storage
    if host_contracts is not None:
        if not isinstance(host_contracts, dict) or set(host_contracts) != set(host_ids):
            raise ValueError("host_contracts must cover exactly the canonical allowed host IDs")
        normalized = {}
        for host in hosts:
            value = host_contracts[host["id"]]
            required = {"command", "environment", "storage"}
            if not isinstance(value, dict) or not required.issubset(value) or set(value) - required - {"env", "allowed_gpu_indices"}:
                raise ValueError("Each host contract requires command, environment and storage; optional env and allowed_gpu_indices")
            argv = value["command"]
            if not isinstance(argv, list) or not argv or len(argv) > 1000 or any(not isinstance(item, str) or "\0" in item or len(item) > 32000 for item in argv) or not argv[0]:
                raise ValueError("Host command must be a nonempty bounded argv array")
            if not isinstance(value["environment"], dict) or not isinstance(value["storage"], dict):
                raise ValueError("Host environment and storage must be explicit objects")
            # Reuse the legacy environment, storage and input validation.
            child = normalize_contract(store, host, argv, {}, [host["id"]], value["environment"], value["storage"], config.get("inputs"))
            row = {"command": list(argv), "environment": child["environment"], "storage": child["storage"]}
            env = value.get("env", {})
            if not isinstance(env, dict) or len(env) > 200 or any(not isinstance(key, str) or not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", key) or key == "CUDA_VISIBLE_DEVICES" or not isinstance(item, str) or "\0" in item or len(item) > 32000 for key, item in env.items()):
                raise ValueError("Host env must map variable names to strings; GPUs are set by the scheduler")
            row["env"] = dict(env)
            if "allowed_gpu_indices" in value:
                indices = value["allowed_gpu_indices"]
                if not isinstance(indices, list) or any(type(item) not in (int, str) or not re.fullmatch(r"[0-9]+", str(item)) for item in indices):
                    raise ValueError("allowed_gpu_indices must be a list of physical GPU indices")
                indices = [str(int(item)) for item in indices]
                if len(indices) != len(set(indices)) or not set(indices).issubset(json.loads(host["gpus"])):
                    raise ValueError("Host allowed_gpu_indices must be unique and authorized on that host")
                row["allowed_gpu_indices"] = indices
            normalized[host["id"]] = row
        config["host_contracts"] = normalized
    return config


def has_contract(run):
    return "allowed_hosts" in json.loads(run["config"])


def candidates(run):
    return json.loads(run["config"]).get("allowed_hosts", [run["host_id"]])


def resolve(run, host_id):
    """One immutable resolution used for admission, resource matching and launch."""
    config = copy.deepcopy(json.loads(run["config"]))
    command = json.loads(run["command"])
    env = json.loads(run["env"])
    if "host_contracts" in config:
        if host_id not in config.get("allowed_hosts", []) or host_id not in config["host_contracts"]:
            raise ValueError("No declared contract for candidate host")
        contract = config["host_contracts"][host_id]
        command = copy.deepcopy(contract["command"])
        env.update(contract.get("env", {}))
        config.update(environment=copy.deepcopy(contract["environment"]), storage=copy.deepcopy(contract["storage"]))
        config["resolved_host_id"] = host_id
        config.pop("allowed_gpu_indices", None)
        if "allowed_gpu_indices" in contract:
            config["allowed_gpu_indices"] = list(contract["allowed_gpu_indices"])
    return {"command": command, "env": env, "config": config}
