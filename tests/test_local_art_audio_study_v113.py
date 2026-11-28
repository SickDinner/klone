"""Analytic regression checks for the local music WAV study."""
from array import array
import contextlib
import hashlib
import io
import json
import math
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
import warnings
import wave

from PIL import Image
from klone.local_art_image_study import analyze_image
from klone.local_art_audio_study import analyze_audio, main


class LocalArtAudioStudyV113(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def save(self, values, rate=8192, channels=1, name="music.wav", width=2):
        path = self.root / name
        data = array("h", values)
        if sys.byteorder != "little":
            data.byteswap()
        with wave.open(str(path), "wb") as f:
            f.setnchannels(channels)
            f.setsampwidth(width)
            f.setframerate(rate)
            f.writeframes(data.tobytes())
        return path

    def test_silence(self):
        r = analyze_audio(self.save([0]*1024))
        self.assertEqual(r["channel_metrics"][0]["rms"],0)
        self.assertIsNone(r["channel_metrics"][0]["crest_factor"])
        self.assertIsNone(r["sampled_spectrum"]["power_centroid_hz"])
        self.assertIsNone(r["sampled_spectrum"]["band_power_fractions"])

    def test_exact_bin_tone(self):
        r = analyze_audio(self.save([0,16384,0,-16384]*256))
        m = r["channel_metrics"][0]
        self.assertAlmostEqual(m["peak"],.5)
        self.assertAlmostEqual(m["rms"],math.sqrt(.125))
        self.assertAlmostEqual(m["crest_factor"],math.sqrt(2))
        self.assertAlmostEqual(m["dc_mean"],0)
        self.assertAlmostEqual(r["sampled_spectrum"]["power_centroid_hz"],2048)
        self.assertAlmostEqual(r["sampled_spectrum"]["band_power_fractions"][2],1)

    def test_dc_and_full_scale(self):
        r = analyze_audio(self.save([-32768]*1024))
        m = r["channel_metrics"][0]
        self.assertEqual(m["peak"],1)
        self.assertEqual(m["rms"],1)
        self.assertEqual(m["dc_mean"],-1)
        self.assertEqual(m["full_scale_sample_count"],1024)
        self.assertAlmostEqual(r["sampled_spectrum"]["power_centroid_hz"],0)

    def test_stereo_anti_phase(self):
        mono = [0,8192,0,-8192]*256
        stereo = [x for v in mono for x in (v,-v)]
        r = analyze_audio(self.save(stereo,channels=2))
        self.assertEqual(r["channel_metrics"][0],r["channel_metrics"][1])
        self.assertGreater(r["channel_metrics"][0]["rms"],0)
        self.assertAlmostEqual(r["sampled_spectrum"]["power_centroid_hz"],2048)

    def test_envelope_and_partial_block(self):
        r = analyze_audio(self.save([0]*800 + [16384]*800 + [8192]*400,rate=8000))
        self.assertEqual(r["envelope"]["rms"],[0,.5,.25])
        self.assertEqual(r["source"]["duration_seconds"],.25)

    def test_window_bound_and_normalization(self):
        r = analyze_audio(self.save([0,8192,0,-8192]*8192))
        s = r["sampled_spectrum"]
        self.assertEqual(s["window_count"],16)
        self.assertEqual(s["bin_spacing_hz"],8)
        self.assertAlmostEqual(sum(s["band_power_fractions"]),1)
        self.assertTrue(all(0 <= v <= 1 for v in s["band_power_fractions"]))

    def test_short_window(self):
        r = analyze_audio(self.save([16384]))
        self.assertEqual(r["sampled_spectrum"]["window_count"],1)
        self.assertTrue(0 <= r["sampled_spectrum"]["power_centroid_hz"] <= 4096)

    def test_invalid_input_limits(self):
        path = self.save([0]*1024)
        with patch("klone.local_art_audio_study.MAX_BYTES",8), self.assertRaises(ValueError):
            analyze_audio(path)
        with patch("klone.local_art_audio_study.MAX_SECONDS",0), self.assertRaises(ValueError):
            analyze_audio(path)
        with self.assertRaises(ValueError):
            analyze_audio(self.save([0]*1024,rate=4000))
        with self.assertRaises(ValueError):
            analyze_audio(self.save([0]*1024,width=1))
        with self.assertRaises(ValueError):
            analyze_audio(self.save([0]*1023,channels=3))

    def test_truncated_data(self):
        path = self.save([0]*1024)
        path.write_bytes(path.read_bytes()[:-10])
        with self.assertRaises(ValueError):
            analyze_audio(path)

    def test_fingerprint_and_replay(self):
        path = self.save([0,16384,0,-16384]*256,name="private_music.wav")
        before = path.read_bytes()
        r = analyze_audio(path)
        self.assertEqual(r["source"]["sha256"],hashlib.sha256(before).hexdigest())
        self.assertNotIn("private_music",json.dumps(r))
        self.assertEqual(r,analyze_audio(path))
        self.assertEqual(before,path.read_bytes())

    def test_cli(self):
        path = self.save([0]*1024)
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            self.assertEqual(main([str(path)]),0)
        self.assertEqual(json.loads(out.getvalue()),analyze_audio(path))
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as caught:
            main([str(self.root/"missing.wav")])
        self.assertEqual(caught.exception.code,2)

    def test_pillow_deprecation_removed(self):
        path = self.root/"image.png"
        Image.new("RGB",(4,4),"white").save(path)
        with warnings.catch_warnings():
            warnings.simplefilter("error",DeprecationWarning)
            self.assertAlmostEqual(analyze_image(path)["metrics"]["mean_relative_luminance"],1)
