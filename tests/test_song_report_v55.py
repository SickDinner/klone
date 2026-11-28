import json
import struct
import tempfile
import unittest
import wave
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path

from klone.song_report import song_report, render_song_html, main
from klone.lyrics_metrics import MAX_BYTES


class SongReportV55(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        self.lyrics = root / "song.txt"
        self.audio = root / "song.wav"
        self.lyrics.write_text("[Chorus]\nPohjoinen yö\nPohjoinen yö", encoding="utf-8")
        with wave.open(str(self.audio), "wb") as out:
            out.setparams((1, 2, 8000, 0, "NONE", "not compressed"))
            out.writeframes(struct.pack("<800h", *([8192, -8192] * 400)))

    def report(self):
        return song_report(self.lyrics, self.audio)

    def test_combined_metrics(self):
        report = self.report()
        self.assertEqual(report["schema"], "klone.song_report.v1")
        self.assertEqual(report["lyrics"]["word_count"], 4)
        self.assertEqual(report["lyrics"]["repeated_line_occurrences"], 1)
        self.assertEqual(report["audio"]["duration_seconds"], 0.1)
        self.assertEqual(report["audio"]["channels"][0]["rms"], 0.25)

    def test_no_alignment_claim(self):
        self.assertIn("No verification that the lyrics match the audio.",
                      self.report()["limitations"])

    def test_repeated_reports_and_unchanged_sources(self):
        before = (self.lyrics.read_bytes(), self.audio.read_bytes())
        self.assertEqual(self.report(), self.report())
        self.assertEqual(before, (self.lyrics.read_bytes(), self.audio.read_bytes()))

    def test_render_sections_and_audio(self):
        html = render_song_html(self.report())
        self.assertIn("Chorus", html)
        self.assertIn("0.25", html)
        self.assertIn("Channel 1", html)
        self.assertIn("No verification", html)

    def test_html_escapes_labels(self):
        self.lyrics.write_text("[<script>alert(1)</script>]\na", encoding="utf-8")
        html = render_song_html(self.report())
        self.assertNotIn("<script>", html)
        self.assertIn("&lt;script&gt;", html)

    def test_html_no_external_assets(self):
        html = render_song_html(self.report())
        for marker in ("http://", "https://", "<script", "<iframe"):
            self.assertNotIn(marker, html)

    def test_cli_json(self):
        out = StringIO()
        with redirect_stdout(out):
            result = main(["--lyrics", str(self.lyrics), "--audio", str(self.audio)])
        self.assertEqual(result, 0)
        self.assertEqual(json.loads(out.getvalue()), self.report())

    def test_oversized_text_rejected(self):
        self.lyrics.write_bytes(b"a" * (MAX_BYTES + 1))
        with self.assertRaises(ValueError):
            self.report()

    def test_invalid_utf8_rejected(self):
        self.lyrics.write_bytes(b"\xff")
        with self.assertRaises(ValueError):
            self.report()

    def test_invalid_audio_rejected(self):
        self.audio.write_bytes(b"")
        with self.assertRaises(EOFError):
            self.report()
