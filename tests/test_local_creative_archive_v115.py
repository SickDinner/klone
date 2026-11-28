"""Tests for the local creative research collection."""
import contextlib
import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import wave

from PIL import Image
from klone.local_creative_archive import creative_archive, main
from klone.local_art_image_study import analyze_image
from klone.local_art_audio_study import analyze_audio
from klone.local_art_lyrics_study import analyze_lyrics


class LocalCreativeArchiveV115(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.image = self.root / "private_image.png"
        Image.new("RGB", (4,4), "blue").save(self.image)
        self.audio = self.root / "private_audio.wav"
        with wave.open(str(self.audio), "wb") as f:
            f.setnchannels(1)
            f.setsampwidth(2)
            f.setframerate(8000)
            f.writeframes(b"\0\0"*1024)
        self.lyrics = self.root / "private_text.txt"
        self.lyrics.write_text("[Chorus]\nUniikkisana kaikuu\n", encoding="utf-8")
        self.items = [("image",self.image),("audio",self.audio),("lyrics",self.lyrics)]

    def test_inventory(self):
        r = creative_archive(self.items)
        self.assertEqual(r["inventory"], {
            "selection_count":3,"unique_record_count":3,
            "duplicate_selection_count":0,
            "records_by_media_kind":{"audio":1,"image":1,"lyrics":1}})
        self.assertEqual(r["schema"],"klone.local_creative_archive.v1")

    def test_preserve_reports(self):
        r = creative_archive(self.items)
        for record, analyze, (_,path) in zip(r["records"],
                (analyze_image,analyze_audio,analyze_lyrics), self.items):
            self.assertEqual(record["report"],analyze(path))
            self.assertEqual(record["report_schema"],record["report"]["schema"])
            self.assertTrue(record["report"]["limitations"])

    def test_fingerprints(self):
        r = creative_archive(self.items)
        for record, (kind,path) in zip(r["records"],self.items):
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            self.assertEqual(record["source_sha256"],digest)
            self.assertEqual(record["record_id"],kind+":"+digest)
            raw = json.dumps(record["report"],ensure_ascii=True,sort_keys=True,
                separators=(",",":"),allow_nan=False).encode("ascii")
            self.assertEqual(record["report_sha256"],hashlib.sha256(raw).hexdigest())

    def test_duplicate_bytes(self):
        copy = self.root/"copy.txt"
        copy.write_bytes(self.lyrics.read_bytes())
        r = creative_archive(self.items+[("lyrics",copy)])
        self.assertEqual(r["inventory"]["unique_record_count"],3)
        self.assertEqual(r["inventory"]["duplicate_selection_count"],1)
        self.assertTrue(r["selections"][3]["duplicate_within_collection"])
        self.assertEqual(r["selections"][3]["record_id"],r["selections"][2]["record_id"])

    def test_equal_descriptors_distinct_bytes(self):
        other = self.root/"other.txt"
        other.write_text(self.lyrics.read_text(encoding="utf-8").upper(), encoding="utf-8")
        r = creative_archive([("lyrics",self.lyrics),("lyrics",other)])
        self.assertEqual(r["inventory"]["unique_record_count"],2)
        a,b = r["records"]
        self.assertEqual(a["report"]["lexical_metrics"],b["report"]["lexical_metrics"])
        self.assertNotEqual(a["source_sha256"],b["source_sha256"])

    def test_order_and_selection_links(self):
        r = creative_archive(list(reversed(self.items))+[self.items[-1]])
        self.assertEqual([x["media_kind"] for x in r["records"]],["lyrics","audio","image"])
        self.assertEqual([x["selection_index"] for x in r["selections"]],[1,2,3,4])
        self.assertEqual(r["selections"][0]["record_id"],r["selections"][3]["record_id"])

    def test_inconsistent_duplicate_report_rejected(self):
        a = analyze_lyrics(self.lyrics)
        b = json.loads(json.dumps(a))
        b["lexical_metrics"]["word_count"] += 1
        with patch("klone.local_creative_archive.analyze_lyrics",side_effect=[a,b]):
            with self.assertRaises(ValueError):
                creative_archive([self.items[-1],self.items[-1]])

    def test_limits(self):
        for items in ([],self.items*5,[("unknown",self.image)]):
            with self.assertRaises(ValueError):
                creative_archive(items)
        with self.assertRaises(OSError):
            creative_archive([("lyrics",self.root/"missing.txt")])

    def test_no_raw_media_paths_or_writes(self):
        before = {p.name:p.read_bytes() for p in self.root.iterdir()}
        r = creative_archive(self.items)
        self.assertEqual(before,{p.name:p.read_bytes() for p in self.root.iterdir()})
        payload = json.dumps(r)
        for text in ("private_image","private_audio","private_text",
                     "Uniikkisana","uniikkisana",str(self.root)):
            self.assertNotIn(text,payload)
        self.assertIsNone(r["records"][1]["report"]["sampled_spectrum"]["power_centroid_hz"])

    def test_cli_replay_and_abort(self):
        args = [v for kind,path in self.items for v in ("--item",kind,str(path))]
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            self.assertEqual(main(args),0)
        self.assertEqual(json.loads(out.getvalue()),creative_archive(self.items))
        self.assertEqual(creative_archive(self.items),creative_archive(self.items))
        failed = io.StringIO()
        with contextlib.redirect_stdout(failed),contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit) as caught:
                main(args+["--item","lyrics",str(self.root/"missing.txt")])
        self.assertEqual(caught.exception.code,2)
        self.assertEqual(failed.getvalue(),"")
