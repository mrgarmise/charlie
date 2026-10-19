"""Synthetic software fixtures for the original-frame sampler/review handoff.

Passing these tests is not authentic score-reader accuracy or a Hailo HEF.
"""
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from PIL import Image, ImageDraw

from experiments.ppal.eyes.calibration import Calibration
from experiments.ppal.inspect_robotron_score import queue_rows, review_game
from experiments.ppal.neural_score.sample import freeze, queue_for_review, role_for_group
from experiments.ppal.score_feedback import reviewed_labels
from memory.evidence import EvidenceJournal


class ScoreSamplerTest(unittest.TestCase):
    def make_fixture(self, base, *, game="game-01", value=2200):
        root = base / "sessions" / "marathon-a" / game
        root.mkdir(parents=True, exist_ok=True)
        image = Image.new("RGB", (640, 480), (9, 9, 9))
        draw = ImageDraw.Draw(image)
        draw.rectangle((80, 65, 160, 95), fill=(200, 200, 200))
        draw.text((90, 67), str(value), fill="white")
        image_file = root / "score-raw-0001.png"
        image.save(image_file)
        log = root / "score.jsonl"
        log.write_text(json.dumps(dict(raw_frame=image_file.name, timestamp=10.25,
                                        score_partition="gameplay", observation_id="observation-a",
                                        p1=dict(observed_score=value, confidence=.51,status="changed"))) + "\n")
        return root

    def test_split_group_is_precommitted_without_label_knowledge(self):
        group = "/game/experiment-run"
        a = role_for_group(group, 17)
        self.assertIn(a, ("train", "val", "test"))
        self.assertEqual(a, role_for_group(group, 17))

    def test_freeze_queue_review_and_human_annotation(self):
        with TemporaryDirectory() as folder:
            base = Path(folder)
            one = self.make_fixture(base, value=2200)
            two = self.make_fixture(base, game="game-02", value=3500)
            # Both games of the same marathon have the same holdout assignment.
            inventory = base / "inventory.json"
            inventory.write_text(json.dumps([
                dict(canonical_game_id="original-game-1",paths=[str(one)]),
                dict(canonical_game_id="original-game-2",paths=[str(two)])]))
            calibration = base / "calibration.json"
            Calibration(((.10,.20),(.90,.20),(.90,.90),(.10,.90))).save(calibration)
            manifest_path = base / "frozen" / "selection.json"
            manifest = freeze(inventory,calibration,manifest_path,limit=10)
            self.assertEqual(len(manifest["selected"]), 2)
            self.assertEqual(len(set(r["role"] for r in manifest["selected"])), 1)
            self.assertEqual(len({r["source_image_sha256"] for r in manifest["selected"]}), 2)
            self.assertTrue(manifest_path.exists())
            source_before = (one / "score.jsonl").read_bytes()
            working = base / "isolated" / "training.sqlite3"
            first = queue_for_review(manifest_path,working)
            self.assertEqual(first["queued"], 2)
            second = queue_for_review(manifest_path,working)
            self.assertEqual(second["already_queued"], 2)
            self.assertEqual((one / "score.jsonl").read_bytes(),source_before)
            journal = EvidenceJournal(working)
            try:
                samples = [r for r in queue_rows(journal) if r.get("sample")]
                self.assertEqual(len(samples), 2)
                self.assertEqual(len(journal.category_records("observation","score_review_proposal")),2)
                role = manifest["selected"][0]["role"]
                part = {"train":"training","val":"validation","test":"final"}[role]
                self.assertEqual(len(reviewed_labels(journal,partition=part)[0]),0)
                review_game(journal,samples[0]["id"],annotator="test-human",
                            verdict="correct",value=2200,reason="Visible whole score",
                            independent=True,not_final_score=True)
                rows,_ = reviewed_labels(journal,partition=part)
                self.assertEqual(len(rows),1)
                self.assertEqual(rows[0]["label"],2200)
            finally:
                journal.close()
            with self.assertRaises(FileExistsError):
                freeze(inventory,calibration,manifest_path,limit=10)

    def test_reject_geometry_without_original_hud(self):
        with TemporaryDirectory() as folder:
            base = Path(folder)
            root = self.make_fixture(base)
            inv = base / "inventory.json"
            inv.write_text(json.dumps([dict(canonical_game_id="g1",paths=[str(root)])]))
            calibration = base / "calibration.json"
            # Extended HUD projects outside the camera exposure.
            Calibration(((.1,.03),(.9,.03),(.9,.9),(.1,.9))).save(calibration)
            m = freeze(inv,calibration,base/"selection.json")
            self.assertEqual(len(m["selected"]),0)
            self.assertGreater(m["exclusions"].get("invalid_or_unusable_frame",0),0)


if __name__ == "__main__":
    unittest.main()
