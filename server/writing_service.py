"""Project-bound compiler integration; LaTeX process ownership lives in latex.py."""
import subprocess
from pathlib import Path

from .surfboards import SurfboardError
from .latex import source_snapshot, extra_sources


class WritingService:
    def latex_status(self, fields):
        if not isinstance(fields, dict):
            raise SurfboardError("Choose a project for the PDF preview.")
        project = self.lookup("projects", fields.get("project_id"))
        result = self.latex.status(project, {key: value for key, value in fields.items() if key != "project_id"})
        result["blocks"] = self.board_record(project["id"], fields.get("experiment_id"))["compiled"].get("latex", [])
        return result

    def latex_action(self, params, scope=None):
        if self.read_only:
            raise SurfboardError("Read-only workspace: compiling and publishing are disabled.", 403)
        if not isinstance(params, dict):
            raise SurfboardError("LaTeX actions need a project and operation.")
        project = self.lookup("projects", params.get("project_id"))
        fields = {key: value for key, value in params.items() if key != "project_id"}
        operation = fields.get("operation", "start")
        agent_scope = scope
        if scope:
            info = self._chat_scope(scope)
            if scope != "manager" and info.get("project_id") != project["id"]:
                raise SurfboardError("The paper belongs to another project.", 403)
            if info["role"] == "worker":
                item = self.experiment_for_scope(scope)
                if fields.get("experiment_id", item["id"]) != item["id"]:
                    raise SurfboardError("The paper belongs to another writing task.", 403)
                fields["experiment_id"] = item["id"]
            if operation not in {"status", "inspect"} and (not self.codex.chat(scope).get("busy") or self.turn_origins.get(scope) != "user"):
                raise SurfboardError("Compiling, stopping or publishing requires active user-requested work.", 403)
        else:
            # The authenticated desktop user may operate their own project or
            # item builds; the module validates item ownership again.
            scope = "experiment:" + fields["experiment_id"] if fields.get("experiment_id") else "project:" + project["id"]
        board = self.board_record(project["id"], fields.get("experiment_id"))
        node_id = fields.pop("node_id", None)
        expected_source = None
        if operation == "start":
            blocks = board["compiled"].get("latex", [])
            if node_id is None and len(blocks) == 1:
                node_id = blocks[0]["node_id"]
            block = next((row for row in blocks if row["node_id"] == node_id), None)
            if not block:
                raise SurfboardError("Select a connected LaTeX block in this project's Surfboard.", 409)
            fields["node_id"] = node_id
            fields.setdefault("main_file", block["main_file"])
            fields.setdefault("source_dir", block.get("source_dir", ""))
            fields["extra_source_files"] = extra_sources(fields.get("extra_source_files", block.get("extra_source_files", [])), fields["source_dir"])
            fields.setdefault("timeout_seconds", block["timeout_seconds"])
            if type(fields["timeout_seconds"]) is not int or not 1 <= fields["timeout_seconds"] <= block["timeout_seconds"]:
                raise SurfboardError("The compile timeout exceeds this LaTeX block's configured limit.")
            operation_key = "compile_latex:" + node_id
            source_gated = any(operation_key in row["applies_to"] and row["kind"] in
                               {"exact_commit", "verified_pr", "check_passed"}
                               for row in board["compiled"]["requirements"])
            # Bind asynchronous compilation to the same bytes admitted by the
            # source gate. Ordinary writing still accepts saved, uncommitted edits.
            if source_gated and fields["extra_source_files"]:
                tracked = subprocess.run(["git", "--literal-pathspecs", "-C", str(Path(project["repo"]).expanduser().resolve()),
                                          "ls-files", "--error-unmatch", "--", *fields["extra_source_files"]],
                                         capture_output=True, timeout=10)
                if tracked.returncode:
                    raise SurfboardError("This LaTeX block requires committed or reviewed source. Additional build files must be tracked by Git; include them in the reviewed source or change the block's source requirement.", 409)
            if source_gated:
                expected_source = source_snapshot(project, fields.get("source_dir", ""), extra_source_files=fields["extra_source_files"])["fingerprint"]
            self.board_gate(project, board, operation_key, fields, agent_scope)
            if source_gated and source_snapshot(project, fields.get("source_dir", ""), extra_source_files=fields["extra_source_files"])["fingerprint"] != expected_source:
                raise SurfboardError("Paper source changed during verification. Verify the current source and compile again.", 409)
        fields.pop("pr_url", None)
        return self.latex.action(scope, project, fields, user=agent_scope is None,
                                 expected_source_fingerprint=expected_source)
