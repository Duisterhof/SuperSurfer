from __future__ import annotations

import asyncio
import base64
import contextlib
import heapq
import itertools
import json
import os
from pathlib import Path
import shlex
import signal
import sys
import time

MAX_SOURCE_PACK_BYTES = 512 * 1024 * 1024

from .ssh_budget import ssh_command

class HostConfigurationError(RuntimeError):
    """A node trust, interpreter or runner protocol error; other nodes can work."""


class ContractGate:
    """One contract at a time, ordered by native queue priority then arrival.

    A cancelled waiter is removed before releasing the condition. Control
    requests do not enter this queue and still share the two-command cap.
    """
    def __init__(self):
        self.condition = asyncio.Condition()
        self.waiters = []
        self.sequence = itertools.count()
        self.held = False

    @contextlib.asynccontextmanager
    async def hold(self, priority=0):
        ticket = (-priority, next(self.sequence))
        async with self.condition:
            heapq.heappush(self.waiters, ticket)
            try:
                await self.condition.wait_for(lambda: not self.held and self.waiters[0] == ticket)
                heapq.heappop(self.waiters)
                self.held = True
            except BaseException:
                self.waiters.remove(ticket)
                heapq.heapify(self.waiters)
                self.condition.notify_all()
                raise
        try:
            yield
        finally:
            async with self.condition:
                self.held = False
                self.condition.notify_all()


class Transport:
    """Each request is bounded; SSH errors retain the manager's reservations."""
    def __init__(self, initial_backoff_seconds=0):
        source = Path(__file__).with_name("runner.py").read_bytes()
        encoded = base64.b64encode(source).decode()
        # This wrapper must parse on old system Python installations, before
        # the modern runner source is compiled. A host configuration error is
        # a structured runner error, not a shared SSH gateway outage.
        self.bootstrap = ("import base64,json,sys\n"
                          "if sys.version_info < (3,9):\n"
                          " print(json.dumps({'ok':False,'error_code':'host_configuration','error':'AML runner requires Python >=3.9; configured interpreter reports '+'.'.join(str(v) for v in sys.version_info[:3])}))\n"
                          " sys.exit(0)\n"
                          "s=base64.b64decode(" + repr(encoded) + ").decode(); "
                          "exec(compile(s,'aml-runner','exec'),"
                          "{'__name__':'__main__','AML_RUNNER_SOURCE':s})")
        self.gateway_locks = {}
        self.gateway_contract_locks = {}
        self.gateway_failures = {}
        self.host_failures = {}
        self.connection_failures = {}
        self.gateway_failed_targets = {}
        self.initial_retry_at = time.monotonic() + initial_backoff_seconds if initial_backoff_seconds else 0

    def clear_host_failure(self, host):
        target = host.get("target")
        self.host_failures.pop(target, None)
        self.connection_failures.pop(target, None)

    def command(self, host, *arguments):
        command = [host["python"], "-c", self.bootstrap, *arguments]
        if host.get("target"):
            command = ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=3", "-o", "ConnectionAttempts=1", "--", host["target"],
                       shlex.join(command)]
        return ssh_command(*command[1:]) if host.get("target") else command

    async def request(self, host, payload, timeout=20):
        target = host.get("target")
        if not target:
            return await self._request(host, payload, timeout)
        # Contracts queue separately so queued preparation cannot occupy both
        # gateway slots ahead of status, allocation probes and launch requests.
        gateway = "trinity" if target.startswith("trinity-") else target
        lock = self.gateway_locks.setdefault(gateway, asyncio.Semaphore(2))
        async with contextlib.AsyncExitStack() as stack:
            if payload.get("op") == "admit":
                contracts = self.gateway_contract_locks.setdefault(gateway, ContractGate())
                await stack.enter_async_context(contracts.hold(payload.get("_admission_priority", 0)))
            await stack.enter_async_context(lock)
            host_retry_at, host_error = self.host_failures.get(target, (0, ""))
            if time.monotonic() < host_retry_at:
                raise HostConfigurationError("Host backoff (five minutes) for " + target + ": " + host_error)
            node_retry, node_error = self.connection_failures.get(target, (0, ""))
            if time.monotonic() < node_retry:
                raise ConnectionError("SSH node backoff (five minutes) for " + target + ": " + node_error)
            retry_at, error = self.gateway_failures.get(gateway, (0, ""))
            if self.initial_retry_at > retry_at:
                retry_at, error = self.initial_retry_at, "Manager startup quiet period"
            if time.monotonic() < retry_at:
                raise ConnectionError("SSH gateway backoff (five minutes): " + error)
            try:
                result = await self._request(host, payload, timeout)
            except HostConfigurationError as exc:
                self.host_failures[target] = (time.monotonic() + 300, str(exc))
                raise
            # Replacing an obsolete admission check deliberately cancels it.
            # _request reaps its process; cancellation is not a node outage.
            except (ConnectionError, TimeoutError) as exc:
                failure = (time.monotonic() + 300, str(exc) or "SSH request timed out or was cancelled")
                self.connection_failures[target] = failure
                failed = self.gateway_failed_targets.setdefault(gateway, set())
                failed.add(target)
                # Two distinct failures without an intervening success indicate
                # a shared outage. Keep both the node and gateway retry bounded.
                if len(failed) >= 2:
                    self.gateway_failures[gateway] = failure
                raise
            self.gateway_failures.pop(gateway, None)
            self.gateway_failed_targets.pop(gateway, None)
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
            first = await asyncio.wait_for(destination.stdout.readline(), 60)
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
            first = await asyncio.wait_for(destination.stdout.readline(), 60)
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
