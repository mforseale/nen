import io
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from deploy_vm import already_installed
from select_runtime import validate_run
from ssh_receive import apply, header, receive_file


class SSHDeploymentTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.payload = b"runtime bytes"
        self.message = {"version": 1, "action": "install", "size": len(self.payload),
                        "sha256": hashlib.sha256(self.payload).hexdigest(), "commit": "a" * 40}

    def test_upload_is_exact_bounded_and_verified(self):
        message = header(io.BytesIO(json.dumps(self.message).encode() + b"\n"))
        destination = self.root / "runtime"
        receive_file(io.BytesIO(self.payload), destination, message)
        self.assertEqual(destination.read_bytes(), self.payload)
        with self.assertRaises(FileExistsError):
            receive_file(io.BytesIO(self.payload), destination, message)

    def test_bad_protocol_size_hash_and_commit_rejected(self):
        for changes in ({"size": 0}, {"size": True}, {"size": 513 * 1024**2}, {"commit": "main; id"},
                        {"sha256": "x" * 64}, {"action": "shell"}, {"version": 2}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                header(io.BytesIO(json.dumps({**self.message, **changes}).encode() + b"\n"))
        with self.assertRaises(ValueError):
            header(io.BytesIO(b" " * 4097 + b"\n"))

    def test_truncated_extra_and_wrong_bytes_rejected(self):
        for payload in (self.payload[:-1], self.payload + b"extra", b"x" * len(self.payload)):
            with self.subTest(payload=payload), self.assertRaises(ValueError):
                receive_file(io.BytesIO(payload), self.root / hashlib.sha256(payload).hexdigest(), self.message)

    def test_worker_only_executes_pinned_installer_and_records_result(self):
        pending = self.root / "pending"
        pending.mkdir()
        (pending / "request.json").write_text(json.dumps({**self.message, "request_id": "test", "command": "/bin/sh"}))
        (pending / "runtime.tar.gz").write_bytes(self.payload)
        with patch("ssh_receive.subprocess.run") as execute:
            execute.return_value.returncode = 0
            self.assertEqual(apply(self.root, Path("/trusted/tools")), 0)
            command = execute.call_args.args[0]
        self.assertEqual(command[:4], ["/usr/bin/python3", "-E", "-s", str(Path("/trusted/tools/deploy_vm.py"))])
        self.assertEqual(command[-2:], ["--expected-commit", "a" * 40])
        self.assertNotIn("/bin/sh", command)
        self.assertEqual(json.loads((self.root / "last-result.json").read_text())["status"], "success")
        self.assertFalse(pending.exists())

    def test_failed_worker_preserves_failure_status(self):
        pending = self.root / "pending"
        pending.mkdir()
        (pending / "request.json").write_text(json.dumps({**self.message, "request_id": "failure"}))
        with patch("ssh_receive.subprocess.run") as execute:
            execute.return_value.returncode = 2
            self.assertEqual(apply(self.root, self.root), 2)
        result = json.loads((self.root / "last-result.json").read_text())
        self.assertEqual((result["status"], result["exit_code"]), ("failure", 2))

    def test_only_successful_own_main_ci_is_deployable(self):
        good = {"workflow_id": 7, "status": "completed", "conclusion": "success", "head_branch": "main",
                "event": "push", "head_sha": "b" * 40,
                "repository": {"full_name": "owner/nen"}, "head_repository": {"full_name": "owner/nen"}}
        self.assertEqual(validate_run(good, "owner/nen", 7), "b" * 40)
        for changes in ({"workflow_id": 8}, {"head_branch": "feature"}, {"event": "pull_request"},
                        {"conclusion": "failure"}, {"status": "in_progress"}, {"head_sha": "main"},
                        {"head_repository": {"full_name": "attacker/nen"}}, {"head_repository": None}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                validate_run({**good, **changes}, "owner/nen", 7)

    def test_same_commit_is_recognized_without_replacing_previous(self):
        self.assertFalse(already_installed(self.root, "a" * 40))
        metadata = self.root / "runtime.json"
        metadata.write_text(json.dumps({"commit": "a" * 40}))
        self.assertTrue(already_installed(self.root, "a" * 40))
        self.assertFalse(already_installed(self.root, "b" * 40))
        metadata.write_text("invalid metadata")
        self.assertFalse(already_installed(self.root, "a" * 40))


if __name__ == "__main__":
    unittest.main()
