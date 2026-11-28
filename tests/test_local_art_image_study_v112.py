"""Analytic checks for bounded local artwork color statistics."""
import contextlib
import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from PIL import Image
from klone.local_art_image_study import analyze_image, main


class LocalArtImageStudyV112(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def save(self, image, name="art.png", **kwargs):
        path = self.root / name
        image.save(path, **kwargs)
        return path

    def test_white_and_black(self):
        for value in (0, 255):
            with self.subTest(value=value):
                path = self.save(Image.new("RGB", (4, 3), (value,) * 3))
                m = analyze_image(path)["metrics"]
                self.assertAlmostEqual(m["mean_relative_luminance"], value / 255)
                self.assertAlmostEqual(m["luminance_population_sd"], 0)
                self.assertEqual(m["occupied_rgb_bins"], 1)
                self.assertEqual(m["rgb_bin_entropy_bits"], 0)

    def test_black_white_split(self):
        im = Image.new("RGB", (4, 2), "black")
        im.paste("white", (2, 0, 4, 2))
        m = analyze_image(self.save(im))["metrics"]
        self.assertAlmostEqual(m["mean_relative_luminance"], .5)
        self.assertAlmostEqual(m["luminance_population_sd"], .5)
        self.assertEqual(m["luminance_histogram_counts"], [4] + [0]*14 + [4])
        self.assertAlmostEqual(m["rgb_bin_entropy_bits"], 1)
        self.assertAlmostEqual(m["left_right_luminance_reflection_error"], 1)
        self.assertEqual(m["top_bottom_luminance_reflection_error"], 0)

    def test_srgb_primary_luminance(self):
        for color, expected in (("red", .2126), ("lime", .7152), ("blue", .0722)):
            with self.subTest(color=color):
                m = analyze_image(self.save(Image.new("RGB", (1,1),color)))["metrics"]
                self.assertAlmostEqual(m["mean_relative_luminance"], expected)

    def test_midgray_linearization(self):
        m = analyze_image(self.save(Image.new("RGB",(1,1),(128,128,128))))["metrics"]
        self.assertAlmostEqual(m["mean_relative_luminance"], .21586050011389926)

    def test_alpha_white_matte(self):
        im = Image.new("RGBA",(2,1),(255,0,0,0))
        m = analyze_image(self.save(im))["metrics"]
        self.assertAlmostEqual(m["mean_relative_luminance"], 1)

    def test_thumbnail_and_accounting(self):
        report = analyze_image(self.save(Image.new("RGB",(512,256),"blue")))
        self.assertEqual(report["source"]["oriented_size"],[512,256])
        self.assertEqual(report["analysis_size"],[256,128])
        self.assertEqual(sum(report["metrics"]["luminance_histogram_counts"]),256*128)

    def test_palette_order_and_coverage(self):
        im = Image.new("RGB",(10,1))
        im.putdata([(i*16,0,0) for i in range(10)])
        m = analyze_image(self.save(im))["metrics"]
        self.assertEqual(m["occupied_rgb_bins"],10)
        self.assertEqual([p["rgb_bin"][0] for p in m["dominant_rgb_bins"]],list(range(8)))
        self.assertAlmostEqual(m["dominant_bin_coverage"],.8)

    def test_jpeg_orientation(self):
        im = Image.new("RGB",(4,2),"red")
        exif = im.getexif()
        exif[274] = 6
        r = analyze_image(self.save(im,"art.jpg",exif=exif))
        self.assertEqual(r["source"]["format"],"JPEG")
        self.assertEqual(r["source"]["oriented_size"],[2,4])
        self.assertEqual(r["analysis_size"],[2,4])

    def test_input_limits(self):
        path = self.save(Image.new("RGB",(4,4)))
        with patch("klone.local_art_image_study.MAX_BYTES", 8):
            with self.assertRaises(ValueError):
                analyze_image(path)
        with patch("klone.local_art_image_study.MAX_PIXELS", 15):
            with self.assertRaises(ValueError):
                analyze_image(path)

    def test_reject_unsupported_and_animated(self):
        path = self.save(Image.new("RGB",(2,2)),"art.gif")
        with self.assertRaises(OSError):
            analyze_image(path)
        first = Image.new("RGB",(2,2),"black")
        second = Image.new("RGB",(2,2),"white")
        path = self.save(first,"animated.png",save_all=True,append_images=[second],duration=100)
        with self.assertRaises(ValueError):
            analyze_image(path)

    def test_fingerprint_and_no_path(self):
        path = self.save(Image.new("RGB",(2,2),"red"),"private_name.png")
        before = path.read_bytes()
        result = analyze_image(path)
        self.assertEqual(result["source"]["sha256"],hashlib.sha256(before).hexdigest())
        self.assertNotIn("private_name",json.dumps(result))
        self.assertEqual(path.read_bytes(),before)
        self.assertEqual(analyze_image(path),result)

    def test_cli(self):
        path = self.save(Image.new("RGB",(2,2),"red"))
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            self.assertEqual(main([str(path)]),0)
        self.assertEqual(json.loads(out.getvalue()),analyze_image(path))
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as caught:
            main([str(self.root / "missing.png")])
        self.assertEqual(caught.exception.code,2)
