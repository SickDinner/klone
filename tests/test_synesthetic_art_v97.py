import io
import json
import math
import struct
import tempfile
import unittest
import wave
import xml.etree.ElementTree as ET
from contextlib import redirect_stdout, redirect_stderr
from pathlib import Path

from klone.synesthetic_art import (
    synesthetic_score, synesthetic_wav, render_synesthetic_svg, main,
)


class SynestheticArtV97(unittest.TestCase):
    def test_score_inventory(self):
        score = synesthetic_score()
        self.assertEqual(score["sample_rate_hz"], 16000)
        self.assertEqual(score["duration_frames"], 32000)
        self.assertEqual([e["midi_note"] for e in score["events"]],
                         [60, 64, 67, 72, 69, 67, 64, 60])

    def test_event_timing(self):
        for i, e in enumerate(synesthetic_score()["events"]):
            self.assertEqual(e["index"], i)
            self.assertEqual(e["start_frame"], 4000 * i)
            self.assertEqual(e["duration_frames"], 4000)

    def test_pitch_and_geometry(self):
        for i, e in enumerate(synesthetic_score()["events"]):
            self.assertAlmostEqual(e["frequency_hz"],
                                   440 * 2 ** ((e["midi_note"] - 69) / 12))
            self.assertEqual(e["angle_degrees"], i * 45)
            self.assertEqual(e["radius"], 48 + 4 * (e["midi_note"] - 60))

    def test_svg_geometry(self):
        root = ET.fromstring(render_synesthetic_svg())
        ns = "{http://www.w3.org/2000/svg}"
        nodes = root.findall(ns + "circle")[1:]
        self.assertEqual(len(nodes), 8)
        self.assertEqual(len(root.findall(ns + "line")), 8)
        for node, e in zip(nodes, synesthetic_score()["events"]):
            x, y = float(node.attrib["cx"]), float(node.attrib["cy"])
            self.assertAlmostEqual(math.hypot(x - 150, y - 150), e["radius"], places=5)
            self.assertEqual(node.attrib["fill"], e["color"])

    def test_pcm_envelopes(self):
        with wave.open(io.BytesIO(synesthetic_wav()), "rb") as src:
            self.assertEqual((src.getnchannels(), src.getsampwidth(), src.getframerate(),
                              src.getnframes()), (1, 2, 16000, 32000))
            samples = struct.unpack("<32000h", src.readframes(32000))
        self.assertTrue(0 < max(map(abs, samples)) <= 5000)
        for i in range(8):
            self.assertEqual(samples[i * 4000], 0)
            self.assertEqual(samples[(i + 1) * 4000 - 1], 0)

    def test_repeatability(self):
        self.assertEqual(synesthetic_score(), synesthetic_score())
        self.assertEqual(synesthetic_wav(), synesthetic_wav())
        self.assertEqual(render_synesthetic_svg(), render_synesthetic_svg())

    def test_cli(self):
        out = io.StringIO()
        with redirect_stdout(out):
            self.assertEqual(main([]), 0)
        self.assertEqual(json.loads(out.getvalue()), synesthetic_score())

    def test_exclusive_output(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "miniature.wav"
            with redirect_stdout(io.StringIO()):
                self.assertEqual(main(["--audio-output", str(path)]), 0)
            self.assertEqual(path.read_bytes(), synesthetic_wav())
            with redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                main(["--audio-output", str(path)])
            self.assertEqual(path.read_bytes(), synesthetic_wav())
