import json
import tempfile
import unittest
import wave
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path

from PIL import Image
from klone.creative_prism import creative_prism, main
from klone.lyrics_metrics import MAX_BYTES


class CreativePrismV74(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        self.art = root / "art.png"
        self.music = root / "music.wav"
        self.lyrics = root / "lyrics.txt"
        Image.new("RGB", (32, 32), "blue").save(self.art)
        self.lyrics.write_text("[Verse]\nPohjoinen yö\nPohjoinen yö", encoding="utf-8")
        with wave.open(str(self.music), "wb") as out:
            out.setparams((1, 2, 8192, 0, "NONE", "not compressed"))
            out.writeframes(bytes(8192 * 2))

    def report(self):
        return creative_prism(self.art, self.music, self.lyrics)

    def test_five_perspectives(self):
        r = self.report()
        self.assertEqual(set(r["perspectives"]), {
            "visual_palette", "lexical_structure", "written_rhythm",
            "audio_dynamics", "leading_clip_spectrum"})
        self.assertEqual(r["schema"], "klone.creative_prism.v1")

    def test_complete_palette(self):
        art = self.report()["perspectives"]["visual_palette"]
        self.assertEqual(art["full_histogram"]["sample_pixels"], 1024)
        self.assertEqual(art["full_histogram"]["bins"], [
            {"rgb_bin": [0, 0, 7], "count": 1024}])

    def test_lexical_and_rhythm_metrics(self):
        p = self.report()["perspectives"]
        self.assertEqual(p["lexical_structure"]["word_count"], 4)
        self.assertEqual(p["written_rhythm"]["written_vowel_groups_per_line"], [4, 4])

    def test_silence_not_spectral_zero(self):
        p = self.report()["perspectives"]
        self.assertEqual(p["audio_dynamics"]["channels"][0]["rms"], 0)
        self.assertIsNone(p["leading_clip_spectrum"]["channels"][0]["spectral_centroid_hz"])

    def test_no_combined_quality_score(self):
        r = self.report()
        self.assertNotIn("quality_score", r)
        self.assertIn("No combined quality score", " ".join(r["limitations"]))

    def test_read_only_and_repeatable(self):
        paths = (self.art, self.music, self.lyrics)
        before = [p.read_bytes() for p in paths]
        self.assertEqual(self.report(), self.report())
        self.assertEqual(before, [p.read_bytes() for p in paths])

    def test_oversized_lyrics_rejected(self):
        self.lyrics.write_bytes(b"a" * (MAX_BYTES + 1))
        with self.assertRaises(ValueError):
            self.report()

    def test_cli_json(self):
        output = StringIO()
        with redirect_stdout(output):
            self.assertEqual(main(["--artwork", str(self.art), "--music",
                                   str(self.music), "--lyrics", str(self.lyrics)]), 0)
        self.assertEqual(json.loads(output.getvalue()), self.report())
