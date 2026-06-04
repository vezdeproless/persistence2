from __future__ import annotations

import contextlib
import io
import json
import os
import stat
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from persist_detector.cli import main


def create_fake_recmd(temp_dir: Path) -> Path:
    fake_py = temp_dir / "fake_recmd.py"
    fake_py.write_text(
        textwrap.dedent(
            """
            from __future__ import annotations

            import json
            import sys
            from pathlib import Path

            args = sys.argv[1:]
            try:
                output_dir = Path(args[args.index("--json") + 1])
                output_name = args[args.index("--jsonf") + 1]
                branch = args[args.index("--kn") + 1]
                hive_path = args[args.index("-f") + 1]
            except (ValueError, IndexError) as error:
                print(f"invalid fake RECmd arguments: {error}", file=sys.stderr)
                raise SystemExit(2)

            output_dir.mkdir(parents=True, exist_ok=True)
            payload = {
                "KeyPath": "ROOT\\\\Microsoft\\\\Windows\\\\CurrentVersion\\\\Run",
                "KeyName": "Run",
                "LastWriteTime": "2026-05-19T12:34:56Z",
                "Values": [
                    {
                        "ValueName": "FakePersistence",
                        "ValueType": "RegSz",
                        "ValueData": " C:\\\\Users\\\\Public\\\\fake-updater.exe ",
                    }
                ],
                "FakeBranch": branch,
                "FakeHivePath": hive_path,
            }
            (output_dir / output_name).write_text(json.dumps(payload), encoding="utf-8")
            """
        ).lstrip(),
        encoding="utf-8",
    )

    if os.name == "nt":
        fake_cmd = temp_dir / "fake_recmd.cmd"
        fake_cmd.write_text(f'@"{sys.executable}" "{fake_py}" %*\n', encoding="utf-8")
        return fake_cmd

    fake_sh = temp_dir / "fake_recmd"
    fake_sh.write_text(f'#!/bin/sh\nexec "{sys.executable}" "{fake_py}" "$@"\n', encoding="utf-8")
    fake_sh.chmod(fake_sh.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    return fake_sh


def create_upload(temp_dir: Path) -> Path:
    upload = temp_dir / "WIN10-LAB_20260519"
    reg_dir = upload / "Reg"
    reg_dir.mkdir(parents=True)
    (reg_dir / "SOFTWARE").write_bytes(b"fake hive content")
    (upload / "manifest.json").write_text(json.dumps({"host_name": "WIN10-LAB"}), encoding="utf-8")
    return upload


def read_registry_records(path: Path) -> list[dict[str, object]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


class ProcessCliTests(unittest.TestCase):
    def test_process_with_fake_recmd_writes_registry_json_and_removes_extracted_dir(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir_name:
            temp_dir = Path(temp_dir_name)
            upload = create_upload(temp_dir)
            fake_recmd = create_fake_recmd(temp_dir)

            with contextlib.redirect_stdout(io.StringIO()):
                exit_code = main(["process", "--input", str(upload), "--recmd", str(fake_recmd), "--skip-index"])

            output = upload / "processed" / "Registry.json"
            records = read_registry_records(output)

            self.assertEqual(exit_code, 0)
            self.assertTrue(output.is_file())
            self.assertGreater(len(records), 0)
            self.assertEqual(records[0]["host.name"], "WIN10-LAB")
            self.assertEqual(records[0]["reg.key.path"], "Software\\Microsoft\\Windows\\CurrentVersion\\Run")
            self.assertEqual(records[0]["file.name"], "FakePersistence")
            self.assertEqual(records[0]["file.path"], "C:\\Users\\Public\\fake-updater.exe")
            self.assertEqual(
                set(records[0]),
                {"@timestamp", "host.name", "reg.key.path", "reg.key.name", "file.name", "file.path"},
            )
            self.assertFalse((upload / "processed" / "extracted").exists())

    def test_process_keep_extracted_preserves_fake_recmd_json(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir_name:
            temp_dir = Path(temp_dir_name)
            upload = create_upload(temp_dir)
            fake_recmd = create_fake_recmd(temp_dir)

            with contextlib.redirect_stdout(io.StringIO()):
                exit_code = main(
                    [
                        "process",
                        "--input",
                        str(upload),
                        "--recmd",
                        str(fake_recmd),
                        "--skip-index",
                        "--keep-extracted",
                    ]
                )

            output = upload / "processed" / "Registry.json"
            extracted_dir = upload / "processed" / "extracted"

            self.assertEqual(exit_code, 0)
            self.assertTrue(output.is_file())
            self.assertGreater(len(read_registry_records(output)), 0)
            self.assertTrue(extracted_dir.is_dir())
            self.assertGreater(len(list(extracted_dir.glob("*.json"))), 0)


if __name__ == "__main__":
    unittest.main()
