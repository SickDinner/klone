"""Regression tests for explicit artwork pair comparisons."""
from array import array
from contextlib import redirect_stdout, redirect_stderr
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
import wave

from PIL import Image
from klone.local_art_comparison import compare_artworks, main


class LocalArtComparisonV116(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def image(self, name, color, size=(4,4)):
        path = self.root / name
        Image.new("RGB", size, color).save(path)
        return path

    def audio(self, name, values, rate=8192, channels=1):
        path = self.root / name
        raw = array("h", values)
        if sys.byteorder != "little":
            raw.byteswap()
        with wave.open(str(path), "wb") as f:
            f.setnchannels(channels)
            f.setsampwidth(2)
            f.setframerate(rate)
            f.writeframes(raw.tobytes())
        return path

    def lyrics(self, name, content):
        path = self.root / name
        path.write_text(content, encoding="utf-8")
        return path

    def metrics(self, kind, a, b):
        return {m["metric"]:m for m in compare_artworks(kind,a,b)["metrics"]}

    def test_image_signed_delta(self):
        a = self.image("black.png","black")
        b = self.image("white.png","white")
        m = self.metrics("image",a,b)["mean_relative_luminance"]
        self.assertEqual(m["status"],"comparable")
        self.assertAlmostEqual(m["delta_second_minus_first"],1)
        self.assertAlmostEqual(self.metrics("image",b,a)["mean_relative_luminance"]["delta_second_minus_first"],-1)

    def test_image_dimensions(self):
        a = self.image("a.png","black")
        b = self.image("b.png","white",(3,4))
        for m in self.metrics("image",a,b).values():
            self.assertEqual(m["status"],"context_mismatch")
            self.assertIsNone(m["delta_second_minus_first"])

    def test_audio_spectrum(self):
        a = self.audio("a.wav",[0,16384,0,-16384]*256)
        b = self.audio("b.wav",[0,0,0,0]*256)
        m = self.metrics("audio",a,b)
        self.assertEqual(m["sampled_power_centroid_hz"]["status"],"undefined")
        self.assertIsNone(m["sampled_power_centroid_hz"]["delta_second_minus_first"])
        self.assertAlmostEqual(m["channel_1.rms"]["delta_second_minus_first"],-(.125**.5))

    def test_audio_compatible_tones(self):
        a = self.audio("a.wav",[0,8192,0,-8192]*256)
        b = self.audio("b.wav",[8192,-8192]*512)
        m = self.metrics("audio",a,b)
        self.assertAlmostEqual(m["sampled_power_centroid_hz"]["first"],2048)
        self.assertAlmostEqual(m["sampled_power_centroid_hz"]["second"],4096)
        self.assertAlmostEqual(m["sampled_power_centroid_hz"]["delta_second_minus_first"],2048)

    def test_audio_context_mismatch(self):
        a = self.audio("a.wav",[0]*1024)
        b = self.audio("b.wav",[0]*2048,channels=2)
        m = self.metrics("audio",a,b)
        self.assertEqual(m["duration_seconds"]["status"],"comparable")
        self.assertEqual(m["duration_seconds"]["delta_second_minus_first"],0)
        self.assertEqual(m["channel_2.rms"]["status"],"context_mismatch")
        self.assertIsNone(m["channel_2.rms"]["first"])
        self.assertIsNone(m["sampled_power_centroid_hz"]["delta_second_minus_first"])

    def test_lyrics_counts_and_fraction(self):
        a = self.lyrics("a.txt","Yö saapuu\n")
        b = self.lyrics("b.txt","Yö saapuu\nYö saapuu\n")
        m = self.metrics("lyrics",a,b)
        self.assertEqual(m["word_count"]["delta_second_minus_first"],2)
        self.assertEqual(m["type_token_ratio"]["delta_second_minus_first"],-.5)
        self.assertEqual(m["repeated_normalized_line_fraction"]["delta_second_minus_first"],.5)
        self.assertIn("Length-sensitive",m["type_token_ratio"]["note"])

    def test_undefined_lyrics(self):
        a = self.lyrics("a.txt","")
        b = self.lyrics("b.txt","Yö")
        m = self.metrics("lyrics",a,b)
        self.assertEqual(m["word_count"]["delta_second_minus_first"],1)
        self.assertIsNone(m["type_token_ratio"]["first"])
        self.assertEqual(m["type_token_ratio"]["status"],"undefined")
        self.assertIsNone(m["type_token_ratio"]["delta_second_minus_first"])

    def test_identity_and_replay(self):
        a = self.lyrics("a.txt","Yö saapuu\n")
        r = compare_artworks("lyrics",a,a)
        self.assertTrue(r["same_source_bytes"])
        self.assertEqual(r["first_record"],r["second_record"])
        self.assertEqual(r,compare_artworks("lyrics",a,a))
        for m in r["metrics"]:
            if m["status"] == "comparable":
                self.assertEqual(m["delta_second_minus_first"],0)

    def test_source_reference_and_privacy(self):
        a = self.lyrics("private_a.txt","Uniikkisana kaikuu")
        b = self.lyrics("private_b.txt","UNIIKKISANA KAIKUU")
        r = compare_artworks("lyrics",a,b)
        self.assertFalse(r["same_source_bytes"])
        self.assertNotEqual(r["first_record"]["source_sha256"],r["second_record"]["source_sha256"])
        self.assertEqual(r["first_record"]["report_schema"],"klone.local_art_lyrics_study.v1")
        self.assertEqual(len(r["first_record"]["report_sha256"]),64)
        self.assertTrue(r["source_limitations"])
        s = json.dumps(r)
        self.assertNotIn("private_a",s)
        self.assertNotIn("uniikkisana",s.lower())

    def test_cli_and_invalid_kind(self):
        a = self.lyrics("a.txt","Yö")
        b = self.lyrics("b.txt","Päivä")
        out = io.StringIO()
        with redirect_stdout(out):
            self.assertEqual(main(["lyrics",str(a),str(b)]),0)
        self.assertEqual(json.loads(out.getvalue()),compare_artworks("lyrics",a,b))
        with self.assertRaises(ValueError):
            compare_artworks("unknown",a,b)
        failed = io.StringIO()
        with redirect_stdout(failed), redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as exc:
            main(["lyrics",str(a),str(self.root/"missing.txt")])
        self.assertEqual(exc.exception.code,2)
        self.assertEqual(failed.getvalue(),"")
