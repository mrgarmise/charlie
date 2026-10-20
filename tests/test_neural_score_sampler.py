"""Synthetic software fixtures for the original-frame sampler/review handoff.

Passing these tests is not authentic score-reader accuracy or a Hailo HEF.
"""
import json
import hashlib
import sqlite3
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from PIL import Image, ImageDraw

from experiments.ppal.eyes.calibration import Calibration
from experiments.ppal.inspect_robotron_score import queue_rows, review_game
from experiments.ppal.neural_score.sample import (freeze, queue_for_review,
    role_for_group, _score_channel_camera_coverage)
from experiments.ppal.neural_score.export_reviews import export
from experiments.ppal.neural_score.attest_reviews import attest
from experiments.ppal.score_review_attestation import attested_photo_annotation_ids
from experiments.ppal.score_observer import ScoreObserver
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

    def test_second_batch_same_session_preserves_split_and_excludes_first_photo(self):
        with TemporaryDirectory() as folder:
            base=Path(folder)
            game=self.make_fixture(base)
            # The next real camera frame has different original pixels and
            # its own source timestamp and log-line identity.
            img=Image.new("RGB",(640,480),(9,9,9))
            dr=ImageDraw.Draw(img)
            dr.rectangle((80,65,190,95),fill=(175,210,200))
            second=game/"score-raw-0002.png"
            img.save(second)
            with (game/"score.jsonl").open("a") as stream:
                stream.write(json.dumps(dict(raw_frame=second.name,
                    timestamp=11.25,score_partition="gameplay",
                    observation_id="observation-b",
                    p1=dict(observed_score=2600,confidence=.72,status="changed")))+"\n")
            inventory=base/"inventory.json"
            inventory.write_text(json.dumps([
                dict(canonical_game_id="recorded-game",paths=[str(game)])]))
            calibration=base/"calibration.json"
            Calibration(((.10,.20),(.90,.20),(.90,.90),(.10,.90))).save(calibration)
            first_file=base/"pilot-1.json"
            first=freeze(inventory,calibration,first_file,limit=1,per_game=1)
            self.assertEqual(len(first["selected"]),1)
            working=base/"isolated"/"working.sqlite3"
            self.assertEqual(queue_for_review(first_file,working)["queued"],1)
            role=first["selected"][0]["role"]
            # Prior review without a frozen split blocks fresh holdout claims.
            blocked=freeze(inventory,calibration,base/"blocked.json",
                           prior_review_journal=working,limit=2,per_game=2)
            self.assertFalse(blocked["selected"])
            # Explicit frozen role allows additional original images from the
            # same session without reusing the old picture.
            second_file=base/"pilot-2.json"
            next_batch=freeze(inventory,calibration,second_file,limit=2,
                              per_game=2,prior=[first_file],
                              prior_review_journal=working)
            self.assertEqual(len(next_batch["selected"]),1, str(next_batch["exclusions"]))
            self.assertEqual(next_batch["selected"][0]["role"],role)
            self.assertNotEqual(next_batch["selected"][0]["source_image_sha256"],
                                first["selected"][0]["source_image_sha256"])
            self.assertEqual(next_batch["exclusions"]["previously_selected_image_excluded"],1)
            self.assertEqual(queue_for_review(second_file,working)["queued"],1)
            self.assertEqual(len([r for r in queue_rows(EvidenceJournal(working,read_only=True))
                                  if r.get("sample")]),2)

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
                            verdict="correct",value=2200,visible_digits="2200",reason="Visible whole score",
                            independent=True,not_final_score=True)
                rows,_ = reviewed_labels(journal,partition=part)
                self.assertEqual(len(rows),1)
                self.assertEqual(rows[0]["label"],2200)
            finally:
                journal.close()
            # Already-reviewed/consulted games are excluded from a new
            # independent holdout sampler on the next version.
            later = freeze(inventory,calibration,base/"fresh-selection.json",
                           prior_review_journal=working,limit=10)
            self.assertFalse(later["selected"])
            self.assertEqual(later["exclusions"]["preconsulted_session_excluded"],2)
            exported=export(working,base/"portable")
            self.assertEqual(exported["photographs"],1)
            # A copied journal on a separate host resolves the relocated
            # hash-addressed photograph without rewriting original IDs.
            # Simulate transfer to Mint: the original Pi paths no longer
            # exist, so only exported hash-addressed images can resolve.
            for game in (one,two):
                original=game/"score-raw-0001.png"
                original.rename(game/"score-raw-0001.png.unavailable")
            saved=EvidenceJournal(base/"portable"/"learning-evidence.sqlite3",read_only=True)
            try:
                proposal=saved.category_records("observation","score_review_proposal")[0]
                recovered=ScoreObserver.review_artifact(saved,proposal.data["payload"])
                self.assertTrue(recovered.is_file())
                self.assertEqual(recovered.parent.name,"images")
            finally:
                saved.close()
            with self.assertRaises(FileExistsError):
                freeze(inventory,calibration,manifest_path,limit=10)

    def test_later_operator_attestation_qualifies_existing_unchanged_labels(self):
        # Regression for a real-world batch where the original photograph
        # was read, but the old UI's redundant checkbox was left unchecked.
        with TemporaryDirectory() as folder:
            base=Path(folder)
            root=self.make_fixture(base)
            manifest_file=base/"pilot.json"
            inventory=base/"inventory.json"
            inventory.write_text(json.dumps([
                dict(canonical_game_id="existing-session",paths=[str(root)])]))
            calibration=base/"calibration.json"
            Calibration(((.10,.20),(.90,.20),(.90,.90),(.10,.90))).save(calibration)
            manifest=freeze(inventory,calibration,manifest_file,limit=1)
            role=manifest["selected"][0]["role"]
            partition={"train":"training","val":"validation","test":"final"}[role]
            location=base/"isolated"/"working.sqlite3"
            self.assertEqual(queue_for_review(manifest_file,location)["queued"],1)
            journal=EvidenceJournal(location)
            try:
                sample=next(row for row in queue_rows(journal) if row.get("sample"))
                review_game(journal,sample["id"],annotator="operator",
                    verdict="correct",value=2200,visible_digits="2200",reason="I read the picture",
                    independent=False,not_final_score=True)
                original=journal.category_records("observation","score_human_annotation")[0]
                original_document=original.document
                self.assertIs(original.data["payload"]["independence_attested"],False)
                self.assertEqual(reviewed_labels(journal,partition=partition)[0],[])
                inspected=attest(journal,manifest_file,apply=False)
                self.assertEqual(inspected["eligible_for_retrospective_photo_attestation"],1)
                self.assertEqual(inspected["appended_attestation_ids"],[])
                result=attest(journal,manifest_file,apply=True)
                self.assertEqual(len(result["appended_attestation_ids"]),1)
                self.assertEqual(journal.get(original.id).document,original_document)
                self.assertEqual(attested_photo_annotation_ids(journal),{original.id})
                self.assertEqual(attest(journal,manifest_file,apply=True)["appended_attestation_ids"],[])
                rows,excluded=reviewed_labels(journal,partition=partition)
                self.assertEqual(len(rows),1)
                self.assertEqual(rows[0]["label"],2200)
                self.assertEqual(rows[0]["annotation_ids"],[original.id])
                self.assertFalse(journal.category_records("event","capability_activation"))
            finally:
                journal.close()
            reloaded=EvidenceJournal(location,read_only=True)
            try:
                self.assertEqual(len(reviewed_labels(reloaded,partition=partition)[0]),1)
                self.assertEqual(len(reloaded.category_records("observation","score_photo_read_attestation")),1)
            finally:
                reloaded.close()

    def test_attestation_refuses_modified_or_missing_original_and_other_batches(self):
        with TemporaryDirectory() as folder:
            base=Path(folder)
            root=self.make_fixture(base)
            inventory=base/"inventory.json"
            inventory.write_text(json.dumps([
                dict(canonical_game_id="g1",paths=[str(root)])]))
            calibration=base/"calibration.json"
            Calibration(((.10,.20),(.90,.20),(.90,.90),(.10,.90))).save(calibration)
            manifest_path=base/"pilot.json"
            freeze(inventory,calibration,manifest_path)
            location=base/"isolated"/"working.sqlite3"
            queue_for_review(manifest_path,location)
            journal=EvidenceJournal(location)
            try:
                sample=next(row for row in queue_rows(journal) if row.get("sample"))
                review_game(journal,sample["id"],annotator="operator",
                    verdict="correct",value=2200,visible_digits="2200",independent=False)
                photo=root/"score-raw-0001.png"
                photo.rename(root/"score-raw-0001.png.missing")
                result=attest(journal,manifest_path,apply=True)
                self.assertFalse(result["appended_attestation_ids"])
                self.assertEqual(result["skipped"]["original_photo_missing_or_modified"],1)
            finally:
                journal.close()

    def test_legacy_midgame_insufficient_recovered_by_explicit_zero_transcription(self):
        # A previous mid-game "not final" click threw away a filled field.
        # We must not create score truth from that lost input. A new
        # photograph-based exact-text correction can preserve visible '00'.
        with TemporaryDirectory() as folder:
            base=Path(folder)
            root=self.make_fixture(base,value=0)
            inventory=base/"inventory.json"
            inventory.write_text(json.dumps([
                dict(canonical_game_id="legacy-midgame-sample",paths=[str(root)])]))
            calibration=base/"calibration.json"
            Calibration(((.10,.20),(.90,.20),(.90,.90),(.10,.90))).save(calibration)
            selection=base/"selection.json"
            plan=freeze(inventory,calibration,selection,limit=1)
            location=base/"isolated"/"working.sqlite3"
            queue_for_review(selection,location)
            j=EvidenceJournal(location)
            try:
                sample=next(row for row in queue_rows(j) if row.get("sample"))
                with self.assertRaisesRegex(ValueError,"mid-game"):
                    review_game(j,sample["id"],annotator="operator",verdict="insufficient")
                with self.assertRaisesRegex(ValueError,"exact"):
                    review_game(j,sample["id"],annotator="operator",verdict="correct",
                                value=0,reason="just numeric zero",independent=True)
                review_game(j,sample["id"],annotator="operator",verdict="correct",
                    value=0,visible_digits="00",reason="read both zero glyphs",
                    independent=True,not_final_score=True)
                part={"train":"training","val":"validation","test":"final"}[plan["selected"][0]["role"]]
                rows,_=reviewed_labels(j,partition=part)
                self.assertEqual(len(rows),1)
                self.assertEqual(rows[0]["label"],0)
                self.assertEqual(rows[0]["display_digits"],"00")
                annotated=j.category_records("observation","score_human_annotation")[-1]
                self.assertEqual(annotated.data["payload"]["visible_digits"],"00")
            finally:
                j.close()

    def test_pre_score_game_uses_hash_bound_original_camera_journal(self):
        with TemporaryDirectory() as folder:
            base = Path(folder)
            root = base / "sessions" / "early-legacy"
            camera_dir = root / "observations"
            camera_dir.mkdir(parents=True)
            frame = camera_dir / "camera-000001.png"
            image = Image.new("RGB",(640,480),(9,9,9))
            draw = ImageDraw.Draw(image)
            draw.rectangle((80,65,160,95),fill=(200,200,200))
            image.save(frame)
            image_sha = hashlib.sha256(frame.read_bytes()).hexdigest()
            journal_file = root / "session-evidence.sqlite3"
            conn = sqlite3.connect(journal_file)
            conn.execute("CREATE TABLE records (id TEXT PRIMARY KEY, document TEXT NOT NULL)")
            doc = dict(kind="observation", episode="original-recorded-episode",
                       at=10.25, payload=dict(category="camera_capture",
                           artifact=dict(path="observations/camera-000001.png",sha256=image_sha),
                           observation_id="camera-observation-001"))
            conn.execute("INSERT INTO records VALUES (?, ?)",("capture-001",json.dumps(doc)))
            conn.commit()
            conn.close()
            calibration = base / "calibration.json"
            Calibration(((.10,.20),(.90,.20),(.90,.90),(.10,.90))).save(calibration)
            inventory = base / "inventory.json"
            inventory.write_text(json.dumps([dict(canonical_game_id="early-original",paths=[str(root)])]))
            manifest_path = base / "selection.json"
            selection = freeze(inventory,calibration,manifest_path)
            self.assertEqual(len(selection["selected"]),1)
            self.assertEqual(selection["selected"][0]["source_reference_record_id"],"capture-001")
            self.assertIsNone(selection["selected"][0]["proposed_score"])
            self.assertEqual(queue_for_review(manifest_path,base/"isolated"/"reviews.sqlite3")["queued"],1)

    def test_real_camera_geometry_keeps_visible_score_channel(self):
        # The released calibration's extended upper-left HUD corner lies just
        # outside the photograph, but *both score channels* are inside it.
        corners=((.24609375,.06527777777777778),
                 (.8125,.11805555555555555),
                 (.8234375,.8263888888888888),
                 (.19375,.7694444444444445))
        self.assertLess(
            corners[0][1] - .10 * (corners[3][1]-corners[0][1]), 0)
        for channel in ((.10,.28),(.72,.90)):
            self.assertGreaterEqual(
                _score_channel_camera_coverage(1280,720,corners,channel),.995)

    def test_clipped_score_channel_stays_ineligible(self):
        corners=((.1,.03),(.9,.03),(.9,.9),(.1,.9))
        self.assertLess(
            _score_channel_camera_coverage(640,480,corners,(.10,.28)),.995)

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
            self.assertGreater(m["exclusions"].get("score_channel_outside_original_camera",0),0)


if __name__ == "__main__":
    unittest.main()
