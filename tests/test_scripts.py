"""Unit checks for drive.py and doctor.py. Run: python -m unittest discover -s tests"""
import json
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent.parent / "skills" / "unity-playtest" / "scripts"
sys.path.insert(0, str(SCRIPTS))

import doctor  # noqa: E402
import drive  # noqa: E402


def make_project(root):
    (root / "ProjectSettings").mkdir(parents=True)
    (root / "ProjectSettings" / "ProjectVersion.txt").write_text("m_EditorVersion: 6000.3.25f1\n")
    (root / "Packages").mkdir()
    (root / "Packages" / "manifest.json").write_text(json.dumps({"dependencies": {"com.unity.pipeline": "0.8.0-exp.1"}}))
    return root


class DriveTests(unittest.TestCase):
    def test_parse_reads_results_and_cli_errors(self):
        self.assertEqual(drive.parse('{"success": true, "result": "ok"}'), (True, {"success": True, "result": "ok"}))
        ok, message = drive.parse('{"success": false, "errors": [{"code": "X", "message": "boom"}]}')
        self.assertFalse(ok)
        self.assertEqual(message, "boom")
        self.assertEqual(drive.parse("not json"), (False, "not json"))

    def test_build_source_orders_prelude_adapter_step_return(self):
        source = drive.build_source("STEP_BODY", "ADAPTER_BODY")
        self.assertLess(source.index("var sb ="), source.index("ADAPTER_BODY"))
        self.assertLess(source.index("ADAPTER_BODY"), source.index("STEP_BODY"))
        self.assertTrue(source.rstrip().endswith("return sb.ToString();"))

    def test_keepalive_is_editor_only(self):
        # Players have no UnityEditor assembly, so the keepalive must stay out of their source.
        self.assertIn("QueuePlayerLoopUpdate", drive.build_source("S", "A"))
        self.assertNotIn("UnityEditor", drive.build_source("S", "A", editor=False))

    def test_find_image_takes_the_base64_payload(self):
        self.assertEqual(drive.find_image({"width": 1280, "png": "A" * 2000, "encoding": "png"}), "A" * 2000)
        self.assertIsNone(drive.find_image({"width": 1280}))

    def test_long_output_keeps_head_and_tail(self):
        with tempfile.TemporaryDirectory() as tmp:
            text = "\n".join(f"line {i}" for i in range(100))
            short = drive.cap_output("probe", text, Path(tmp))
            self.assertIn("line 0", short)
            self.assertIn("line 99", short)
            self.assertNotIn("line 50\n", short)
            self.assertEqual((Path(tmp) / "out" / "probe.txt").read_text(encoding="utf-8"), text)

    def test_player_capture_waits_for_the_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            work = Path(tmp)
            def fake_unity(args, player=None, **_):
                path = args[2].split('"')[1]
                Path(path).write_bytes(b"png")
                return True, {"result": "ok"}
            real, drive.unity = drive.unity, fake_unity
            try:
                line = drive.run_step("cap:client", work, "build")
            finally:
                drive.unity = real
            self.assertIn("saved", line)
            self.assertTrue((work / "shots" / "client.png").is_file())

    def test_until_polls_past_waiting(self):
        answers = iter(["waiting", "waiting", "0.120 s, 7 frames"])
        real_unity, real_sleep = drive.unity, drive.time.sleep
        drive.unity, drive.time.sleep = (lambda *a, **k: (True, {"result": next(answers)})), (lambda _: None)
        try:
            self.assertEqual(drive.run_step("until:door", Path("w"), None), "[until:door] 0.120 s, 7 frames")
        finally:
            drive.unity, drive.time.sleep = real_unity, real_sleep

    def test_falls_back_to_flat_names_on_pipeline_08(self):
        calls = []
        def fake_run(cmd, **_):
            calls.append(cmd)
            grouped = "script" in cmd
            out = '{"success": false, "errors": [{"message": "Command Not Found"}]}' if grouped else '{"result": "ok"}'
            return type("Done", (), {"stdout": out, "stderr": ""})()
        real_run, real_which = drive.subprocess.run, drive.shutil.which
        drive.subprocess.run, drive.shutil.which, drive._grouped = fake_run, (lambda _: "unity"), None
        try:
            self.assertEqual(drive.unity(["eval", "--code", "x"]), (True, {"result": "ok"}))
            self.assertFalse(drive._grouped)
            drive.unity(["eval", "--code", "y"])
            self.assertEqual(len(calls), 3)  # grouped, flat, then flat only
        finally:
            drive.subprocess.run, drive.shutil.which, drive._grouped = real_run, real_which, None

    def test_find_project_walks_up(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = make_project(Path(tmp))
            (root / "Assets" / "Scripts").mkdir(parents=True)
            self.assertEqual(drive.find_project(root / "Assets" / "Scripts"), root.resolve())


class DoctorTests(unittest.TestCase):
    def test_init_creates_a_folder_git_ignores_by_itself(self):
        with tempfile.TemporaryDirectory() as tmp:
            work = doctor.init_workspace(make_project(Path(tmp)))
            self.assertEqual((work / ".gitignore").read_text().splitlines()[-1], "*")
            for name in ("steps", "shots", "builds", "PROJECT.md", "CHECKLIST.md", "REPORT.md", "adapter.cs"):
                self.assertTrue((work / name).exists(), name)

    def test_runtime_left_enabled_in_builds_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = make_project(Path(tmp))
            config = root / doctor.RUNTIME_CONFIG
            config.parent.mkdir(parents=True)
            config.write_text(json.dumps({"enableInBuilds": True}))
            self.assertIn("FAIL", [level for level, _ in doctor.leftovers(root)])
            config.write_text(json.dumps({"enableInBuilds": False}))
            self.assertFalse([m for level, m in doctor.leftovers(root) if level == "FAIL"])
            config.write_text(json.dumps({"enableInDevelopmentBuilds": True, "enableInReleaseBuilds": False}))
            self.assertTrue([m for level, m in doctor.leftovers(root) if level == "FAIL"])
            config.write_text(json.dumps({"enableInBuilds": False}))
            self.assertEqual(doctor.leftovers(root), [])
            (root / "ProjectSettings" / "ProjectSettings.asset").write_text("    Standalone: ENABLE_RUNTIME_PIPELINE_DEV\n")
            self.assertIn("FAIL", [level for level, _ in doctor.leftovers(root)])

    def test_editor_row_matches_the_path_exactly(self):
        with tempfile.TemporaryDirectory() as tmp:
            game = Path(tmp).resolve() / "Game"
            listing = "\n".join([
                "Project\tPath\tPID\tRunning\tPipeline\tVersion\tUpdate\tPort\tServer Reachable\tSafe Mode",
                f"Game-B\t{game}-B\t2\ttrue\ttrue\t0.8\ttrue\t7800\tfalse\t",
                f"Game\t{game}\t1\ttrue\ttrue\t0.8\ttrue\t7800\ttrue\t",
            ])
            self.assertEqual(doctor.editor_row(listing, game)[0], "Game")
            self.assertEqual(doctor.editor_row(listing, Path(tmp) / "Other"), [])

    def test_screenshot_leftovers_warn(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = make_project(Path(tmp))
            (root / "Assets" / "Temp").mkdir(parents=True)
            self.assertEqual([level for level, _ in doctor.leftovers(root)], ["WARN"])


if __name__ == "__main__":
    unittest.main()
