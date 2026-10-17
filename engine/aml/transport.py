from __future__ import annotations

import asyncio
import base64
import hashlib
import json
import os
from pathlib import Path
import shlex
import signal
import sys
import tempfile
import time

MAX_SOURCE_PACK_BYTES = 512 * 1024 * 1024
SSH_IDLE_SECONDS = 600
SSH_CONNECT_TIMEOUT = 15
RECEIVER_READY_TIMEOUT = 45

class HostConfigurationError(RuntimeError):
    """A node trust, interpreter or runner protocol error; other nodes can work."""


class Transport:
    """Each request is bounded; SSH errors retain the manager's reservations."""
    def __init__(self, initial_backoff_seconds=0):
        source = Path(__file__).with_name("runner.py").read_bytes()
        encoded = base64.b64encode(source).decode()
        slurm_source = Path(__file__).with_name("slurm_bridge.py").read_text()

        # This wrapper must parse on old system Python installations, before
        # the modern runner source is compiled. A host configuration error is
        # a structured runner error, not a shared SSH gateway outage.
        self.bootstrap = ("import base64,json,sys\n"
                          "if sys.version_info < (3,9):\n"
                          " print(json.dumps({'ok':False,'error_code':'host_configuration','error':'AML runner requires Python >=3.9; configured interpreter reports '+'.'.join(str(v) for v in sys.version_info[:3])}))\n"
                          " sys.exit(0)\n"
                          "s=base64.b64decode(" + repr(encoded) + ").decode(); "
                          "exec(compile(s,'aml-runner','exec'),"
                          "{'__name__':'__main__','AML_RUNNER_SOURCE':s,'AML_SLURM_SOURCE':" + repr(slurm_source) + "})")
        self.gateway_locks = {}
        self.host_failures = {}
        self.connection_failures = {}
        self.initial_retry_at = time.monotonic() + initial_backoff_seconds if initial_backoff_seconds else 0
        self.control_directory = None
        self.closed = False

    def clear_host_failure(self, host):
        target = host.get("target")
        self.host_failures.pop(target, None)
        self.connection_failures.pop(target, None)

    def command(self, host, *arguments):
        if self.closed:
            raise RuntimeError("Transport is closed")
        command = [host["python"], "-c", self.bootstrap, *arguments]
        if host.get("target"):
            if self.control_directory is None:
                # A private, short local path avoids Unix socket path limits and
                # never attaches to the user's interactive SSH control masters.
                self.control_directory = tempfile.TemporaryDirectory(prefix="ss-ssh-", dir="/tmp")
            alias = hashlib.sha256(host["target"].encode()).hexdigest()[:12]
            control = str(Path(self.control_directory.name) / (alias + "-%C.sock"))
            command = ["ssh", "-T", "-o", "BatchMode=yes", "-o", f"ConnectTimeout={SSH_CONNECT_TIMEOUT}",
                       "-o", "ConnectionAttempts=1", "-o", "ClearAllForwardings=yes",
                       "-o", "ControlMaster=auto", "-o", f"ControlPath={control}",
                       "-o", f"ControlPersist={SSH_IDLE_SECONDS}",
                       "-o", "ServerAliveInterval=15", "-o", "ServerAliveCountMax=2", "--", host["target"],
                       shlex.join(command)]
        return command

    async def close(self):
        """Close only this manager's reusable connections, without logging in."""
        self.closed = True
        if self.control_directory is None:
            return
        directory, self.control_directory = self.control_directory, None

        async def stop_master(socket):
            process = await asyncio.create_subprocess_exec(
                "ssh", "-F", os.devnull, "-S", str(socket), "-O", "exit", "localhost",
                stdin=asyncio.subprocess.DEVNULL, stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL)
            try:
                await asyncio.wait_for(process.wait(), 2)
            finally:
                if process.returncode is None:
                    process.kill()
                    await process.wait()

        try:
            await asyncio.gather(*(stop_master(socket) for socket in Path(directory.name).glob("*.sock")),
                                 return_exceptions=True)
        finally:
            directory.cleanup()

    async def request(self, host, payload, timeout=45):
        target = host.get("target")
        if not target:
            return await asyncio.wait_for(self._request(host, payload, timeout), timeout)
        # Trinity worker aliases share one SSH gateway. Serialize its control
        # requests. One unreachable node must not block healthy peers behind it.
        gateway = "trinity" if target.startswith("trinity-") else target
        lock = self.gateway_locks.setdefault(gateway, asyncio.Lock())
        async with lock:
            host_retry_at, host_error = self.host_failures.get(target, (0, ""))
            if time.monotonic() < host_retry_at:
                raise HostConfigurationError("Host backoff (five minutes) for " + target + ": " + host_error)
            node_retry, node_error = self.connection_failures.get(target, (0, ""))
            if time.monotonic() < node_retry:
                raise ConnectionError("SSH node backoff (five minutes) for " + target + ": " + node_error)
            if time.monotonic() < self.initial_retry_at:
                raise ConnectionError("Manager startup quiet period")
            try:
                # The deadline starts after admission to the gateway, rather
                # than counting time waiting behind another node's request.
                result = await asyncio.wait_for(self._request(host, payload, timeout), timeout)
            except HostConfigurationError as exc:
                self.host_failures[target] = (time.monotonic() + 300, str(exc))
                raise
            # Replacing an obsolete admission check deliberately cancels it.
            # _request reaps its process; cancellation is not a node outage.
            except TimeoutError as exc:
                # A slow runner or cold SSH handshake is node-specific
                # evidence, not proof that every peer's gateway is down.
                error = f"{payload.get('op', 'Runner request')} exceeded {timeout:g}s on {target}"
                self.connection_failures[target] = (time.monotonic() + 300, error)
                raise TimeoutError(error) from exc
            except ConnectionError as exc:
                # A relay can reset individual destinations while other nodes
                # remain reachable. Do not infer a gateway outage from peers.
                self.connection_failures[target] = (time.monotonic() + 300, str(exc))
                raise
            self.connection_failures.pop(target, None)
            self.host_failures.pop(target, None)
            return result

    async def _request(self, host, payload, timeout):
        command = self.command(host)
        process = await asyncio.create_subprocess_exec(*command, stdin=asyncio.subprocess.PIPE,
                                                      stdout=asyncio.subprocess.PIPE,
                                                      stderr=asyncio.subprocess.PIPE, start_new_session=True)
        try:
            out, err = await asyncio.wait_for(process.communicate(json.dumps(payload).encode()), timeout)
        except BaseException:
            if process.returncode is None:
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
            await process.wait()
            raise
        try:
            response = json.loads(out)
        except ValueError:
            diagnostic = err.decode(errors="replace").strip() or "Invalid runner response"
            host_key_error = any(marker in diagnostic.lower() for marker in
                                 ("host key verification failed", "remote host identification has changed",
                                  "host key is known for"))
            if host_key_error or process.returncode != 255:
                raise HostConfigurationError(diagnostic)
            raise ConnectionError(diagnostic)
        if not isinstance(response, dict) or type(response.get("ok")) is not bool:
            raise HostConfigurationError("Invalid runner response object")
        if not response.get("ok"):
            if response.get("error_code") == "host_configuration":
                raise HostConfigurationError(response.get("error", "Invalid host configuration"))
            raise RuntimeError(response.get("error", "Runner failed"))
        if "result" not in response:
            raise HostConfigurationError("Runner response is missing result")
        return response["result"]


    async def copy_file(self, source_host, destination_host, item, storage, timeout=600):
        """Stream only declared bytes; the receiver verifies and commits atomically."""
        source_host = source_host or {"python": sys.executable, "target": None}
        options = json.dumps({"input": item, "storage": storage})
        destination = await asyncio.create_subprocess_exec(
            *self.command(destination_host, "__receive", options), stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
        source = None
        async def transfer():
            nonlocal source
            first = await asyncio.wait_for(destination.stdout.readline(), RECEIVER_READY_TIMEOUT)
            if not first or not json.loads(first).get("ready"):
                error = (await destination.stderr.read()).decode(errors="replace")
                raise RuntimeError(error.strip() or "Destination refused staging")
            source = await asyncio.create_subprocess_exec(
                *self.command(source_host, "__send", options), stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE)
            sent = 0
            while chunk := await source.stdout.read(65536):
                sent += len(chunk)
                if sent > item["size_bytes"]:
                    raise ValueError("Source exceeded the declared byte budget")
                destination.stdin.write(chunk)
                await destination.stdin.drain()
            destination.stdin.close()
            source_error = (await source.stderr.read()).decode(errors="replace")
            await source.wait()
            if source.returncode:
                raise RuntimeError(source_error.strip() or "Source transfer failed")
            output, error = await destination.communicate()
            if destination.returncode:
                raise RuntimeError(error.decode(errors="replace").strip() or "Destination verification failed")
            result = json.loads(output)
            if not result.get("ready") or sent != item["size_bytes"]:
                raise RuntimeError("Input transfer was incomplete")
            return result
        try:
            return await asyncio.wait_for(transfer(), timeout)
        finally:
            for process in (source, destination):
                if process is None or process.returncode is not None:
                    continue
                process.terminate()
                try:
                    await asyncio.wait_for(process.wait(), 2)
                except TimeoutError:
                    process.kill()
                    await process.wait()

    async def stage_source(self, source_repo, host, spec, timeout=600):
        """Transfer only the recorded commit's reachable objects; change no refs."""
        options = {key: spec[key] for key in ("repo", "revision")}
        options["config"] = {key: spec["config"][key] for key in ("pr_url", "review_receipt", "review_repository") if key in spec["config"]}
        destination = await asyncio.create_subprocess_exec(
            *self.command(host, "__receive_source", json.dumps(options)), stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
        source = None
        async def transfer():
            nonlocal source
            first = await asyncio.wait_for(destination.stdout.readline(), RECEIVER_READY_TIMEOUT)
            if not first:
                _, error = await destination.communicate()
                raise RuntimeError(error.decode(errors="replace")[-2000:] or "Node refused source staging")
            ready = json.loads(first)
            if not ready.get("ready"):
                raise RuntimeError("Node refused source staging")
            if ready.get("already_present"):
                await destination.wait()
                return ready
            source = await asyncio.create_subprocess_exec(
                "git", "-C", source_repo, "pack-objects", "--quiet", "--stdout", "--revs",
                stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
            source.stdin.write((spec["revision"] + "\n").encode())
            await source.stdin.drain()
            source.stdin.close()
            sent = 0
            while chunk := await source.stdout.read(65536):
                sent += len(chunk)
                if sent > MAX_SOURCE_PACK_BYTES:
                    raise ValueError("Exact-source pack exceeds the 512 MiB staging limit")
                destination.stdin.write(chunk)
                await destination.stdin.drain()
            _, error = await source.communicate()
            if source.returncode:
                raise RuntimeError(error.decode(errors="replace")[-2000:] or "Could not pack the recorded source revision")
            destination.stdin.close()
            output, error = await destination.communicate()
            if destination.returncode:
                raise RuntimeError(error.decode(errors="replace")[-2000:] or "Node could not import the recorded source revision")
            result = json.loads(output)
            if not result.get("ready") or result.get("revision") != spec["revision"]:
                raise RuntimeError("Node did not confirm the exact source revision")
            return result
        try:
            return await asyncio.wait_for(transfer(), timeout)
        finally:
            for process in (source, destination):
                if process is None or process.returncode is not None:
                    continue
                process.terminate()
                try:
                    await asyncio.wait_for(process.wait(), 2)
                except TimeoutError:
                    process.kill()
                    await process.wait()
