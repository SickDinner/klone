import io
import json
import struct
import tempfile
import unittest
import wave
from contextlib import redirect_stdout, redirect_stderr
from pathlib import Path

from klone.palette_melody import palette_score, palette_wav, main, NOTE_FRAMES


class PaletteMelodyV81(unittest.TestCase):
    def test_dusk_mapping(self):
        score = palette_score("dusk")
        self.assertEqual([n["midi_note"] for n in score["notes"]], [69, 81, 76])
        self.assertEqual(score["notes"][0]["frequency_hz"], 440)

    def test_winter_distinct(self):
        self.assertNotEqual(palette_score("dusk")["notes"], palette_score("winter")["notes"])

    def test_frequency_relation(self):
        for name in ("dusk", "winter"):
            for note in palette_score(name)["notes"]:
                self.assertAlmostEqual(note["frequency_hz"],
                    440 * 2 ** ((note["midi_note"] - 69) / 12), places=7)

    def test_pcm_and_envelope(self):
        with wave.open(io.BytesIO(palette_wav()), "rb") as source:
            self.assertEqual((source.getnchannels(), source.getsampwidth(),
                              source.getframerate(), source.getnframes()),
                             (1, 2, 16000, 12000))
            values = struct.unpack("<12000h", source.readframes(12000))
        self.assertLessEqual(max(map(abs, values)), 5000)
        self.assertGreater(max(map(abs, values)), 1000)
        for i in range(3):
            self.assertEqual(values[i * NOTE_FRAMES], 0)
            self.assertEqual(values[(i + 1) * NOTE_FRAMES - 1], 0)

    def test_deterministic(self):
        self.assertEqual(palette_wav("winter"), palette_wav("winter"))
        self.assertNotEqual(palette_wav("winter"), palette_wav("dusk"))

    def test_invalid_palette(self):
        for name in ("unknown", None, []):
            with self.assertRaises(ValueError):
                palette_score(name)

    def test_cli_json(self):
        output = io.StringIO()
        with redirect_stdout(output):
            self.assertEqual(main(["--palette", "winter"]), 0)
        self.assertEqual(json.loads(output.getvalue()), palette_score("winter"))

    def test_cli_preserves_existing_output(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "melody.wav"
            with redirect_stdout(io.StringIO()):
                self.assertEqual(main(["--output", str(path)]), 0)
            original = path.read_bytes()
            self.assertEqual(original, palette_wav())
            with redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                main(["--output", str(path)])
            self.assertEqual(path.read_bytes(), original)
