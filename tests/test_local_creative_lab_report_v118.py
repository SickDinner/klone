"""Regression tests for the offline creative laboratory."""
from contextlib import redirect_stdout, redirect_stderr
import copy
from html.parser import HTMLParser
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import wave

from PIL import Image
from klone.local_creative_lab_report import build_lab, main, render_lab
from klone.local_creative_archive import creative_archive
from klone.local_art_comparison import compare_artworks
from klone.art_metric_validation import validation_study


class Document(HTMLParser):
    def __init__(self, html):
        super().__init__()
        self.tags = []
        self.blocks = []
        self.in_pre = False
        self.feed(html)
        self.close()

    def handle_starttag(self, tag, attrs):
        self.tags.append((tag,dict(attrs)))
        if tag == "pre":
            self.blocks.append("")
            self.in_pre = True

    def handle_endtag(self, tag):
        if tag == "pre":
            self.in_pre = False

    def handle_data(self, data):
        if self.in_pre:
            self.blocks[-1] += data


class LocalCreativeLabReportV118(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        temp = tempfile.TemporaryDirectory()
        cls.addClassCleanup(temp.cleanup)
        root = Path(temp.name)
        cls.image = root / "private_image.png"
        Image.new("RGB",(8,8),"blue").save(cls.image)
        cls.audio = root / "private_audio.wav"
        with wave.open(str(cls.audio),"wb") as f:
            f.setnchannels(1)
            f.setsampwidth(2)
            f.setframerate(8192)
            f.writeframes(b"\0\0"*1024)
        cls.lyrics = root / "private_lyrics.txt"
        cls.lyrics.write_text("Uniikkisana kaikuu\n",encoding="utf-8")
        cls.items = [("image",cls.image),("audio",cls.audio),
                     ("lyrics",cls.lyrics),("lyrics",cls.lyrics)]
        cls.pairs = [("lyrics",cls.lyrics,cls.lyrics)]
        cls.archive = creative_archive(cls.items)
        cls.comparisons = [compare_artworks(*cls.pairs[0])]
        cls.validation = validation_study()
        cls.html = render_lab(cls.archive,cls.comparisons,cls.validation)
        cls.doc = Document(cls.html)

    def test_document_and_navigation(self):
        self.assertTrue(self.html.startswith("<!doctype html>"))
        self.assertTrue(self.html.endswith("</body></html>"))
        ids = [a["id"] for t,a in self.doc.tags if "id" in a]
        links = [a["href"] for t,a in self.doc.tags if t=="a"]
        self.assertEqual(len(ids),5)
        self.assertEqual(set(links),{"#"+i for i in ids})
        self.assertEqual(sum(t=="article" for t,a in self.doc.tags),4)

    def test_inventory(self):
        for value,label in ((4,"Selections"),(3,"Unique records"),
                            (1,"Duplicate selections"),(1,"Comparisons")):
            self.assertIn("<strong>"+str(value)+"</strong>"+label,self.html)

    def test_all_source_payloads_preserved(self):
        blocks = [json.loads(b) for b in self.doc.blocks]
        for r in self.archive["records"]:
            self.assertIn(r,blocks)
            self.assertIn(r["source_sha256"],self.html)
        self.assertIn(self.archive,blocks)
        self.assertIn(self.comparisons[0],blocks)
        self.assertIn(self.validation,blocks)

    def test_descriptor_sections(self):
        for text in ("mean_relative_luminance","Fixed RGB palette bins",
                     "Digital channel levels","Written lyric descriptors",
                     "type_token_ratio","image_equal_distribution","Undefined"):
            self.assertIn(text,self.html)

    def test_no_active_content(self):
        for tag,attrs in self.doc.tags:
            self.assertNotIn(tag,{"script","iframe","object","embed","img","form","link"})
            self.assertNotIn("src",attrs)
            self.assertFalse(any(k.startswith("on") for k in attrs))
            if "href" in attrs:
                self.assertTrue(attrs["href"].startswith("#"))
        csp = [a["content"] for t,a in self.doc.tags
               if t=="meta" and a.get("http-equiv")=="Content-Security-Policy"]
        self.assertEqual(len(csp),1)
        self.assertIn("default-src 'none'",csp[0])

    def test_escape(self):
        validation = copy.deepcopy(self.validation)
        validation["checks"][0]["scope"] = '<script>alert("x")</script>'
        html = render_lab(self.archive,self.comparisons,validation)
        self.assertNotIn("<script>",html)
        self.assertIn("&lt;script&gt;",html)
        self.assertIn(validation,[json.loads(b) for b in Document(html).blocks])

    def test_privacy_and_no_mutation(self):
        self.assertNotIn("private_lyrics",self.html)
        self.assertNotIn("Uniikkisana",self.html)
        self.assertNotIn(str(self.lyrics.parent),self.html)
        before = copy.deepcopy((self.archive,self.comparisons,self.validation))
        self.assertEqual(render_lab(*before),self.html)
        self.assertEqual(before,(self.archive,self.comparisons,self.validation))

    def test_build_and_replay(self):
        self.assertEqual(build_lab(self.items,self.pairs),(self.html,0))
        self.assertEqual(build_lab(self.items,self.pairs),(self.html,0))
        html,failures = build_lab(self.items)
        self.assertEqual(failures,0)
        self.assertIn("No comparisons selected.",html)

    def test_failed_validation_visible_and_nonzero(self):
        validation = copy.deepcopy(self.validation)
        validation["checks"][0]["status"] = "failed"
        validation["status_counts"] = {"failed":1,"passed":9}
        out = io.StringIO()
        with patch("klone.local_creative_lab_report.validation_study",return_value=validation):
            with redirect_stdout(out):
                self.assertEqual(main(["--item","lyrics",str(self.lyrics)]),1)
        self.assertIn("<td>failed</td>",out.getvalue())
        self.assertIn(validation,[json.loads(b) for b in Document(out.getvalue()).blocks])

    def test_limits_and_cli(self):
        with self.assertRaises(ValueError):
            build_lab(self.items,self.pairs*4)
        args = [v for kind,path in self.items for v in ("--item",kind,str(path))]
        args += ["--compare","lyrics",str(self.lyrics),str(self.lyrics)]
        out = io.StringIO()
        with redirect_stdout(out):
            self.assertEqual(main(args),0)
        self.assertEqual(out.getvalue(),self.html+"\n")
        failed = io.StringIO()
        with redirect_stdout(failed),redirect_stderr(io.StringIO()),self.assertRaises(SystemExit) as exc:
            main(["--item","lyrics",str(self.lyrics.parent/"missing.txt")])
        self.assertEqual(exc.exception.code,2)
        self.assertEqual(failed.getvalue(),"")
