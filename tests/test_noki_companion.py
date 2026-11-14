"""Noki: opt-in companion, public-source index and voice rack regression checks."""
import json
import unittest

from fastapi.testclient import TestClient

from klone.main import create_app


class NokiCompanionTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(create_app())

    def get_html(self):
        response = self.client.get("/noki")
        self.assertEqual(response.status_code, 200)
        return response.text

    def get_static(self, name):
        response = self.client.get("/static/" + name)
        self.assertEqual(response.status_code, 200, name)
        return response

    def test_noki_page_is_served_in_finnish(self):
        html = self.get_html()
        self.assertIn('lang="fi"', html)
        self.assertIn("Noki v0.4", html)
        self.assertIn("Taidelaboratorio", html)

    def test_read_only_grimoire_has_72_goetia_spirits_and_sources(self):
        data = self.get_static("noki-grimoire.json").json()
        self.assertEqual(data["schema_version"], 1)
        self.assertEqual(len(data["spirits"]), 72)
        self.assertEqual([s["order"] for s in data["spirits"]], list(range(1, 73)))
        self.assertEqual(data["spirits"][8]["name"], "Paimon")
        self.assertEqual(data["spirits"][23]["name"], "Naberius")
        self.assertEqual(data["spirits"][-1]["name"], "Andromalius")
        self.assertGreaterEqual(len(data["entries"]), 60)
        self.assertGreaterEqual(len(data["sources"]), 15)
        self.assertEqual(data["total_entries"], len(data["entries"]) + 72)
        self.assertEqual(len({s["id"] for s in data["sources"]}), len(data["sources"]))
        self.assertEqual(len({e["id"] for e in data["entries"]}), len(data["entries"]))
        ids = {s["id"] for s in data["sources"]}
        for item in data["entries"] + data["spirits"]:
            self.assertTrue(item["sources"])
            self.assertTrue(set(item["sources"]).issubset(ids))
        for source in data["sources"]:
            self.assertTrue(source["url"].startswith("https://"))

    def test_vodou_and_psychedelic_sources_stay_distinct(self):
        data = self.get_static("noki-grimoire.json").json()
        vodou = " ".join(e["summary"] for e in data["entries"] if e["category"] == "vodou")
        self.assertIn("elävä uskonto", vodou)
        self.assertIn("eivät ole Ars Goetian demoneita", vodou)
        psychedelic = [e for e in data["entries"] if e["category"] == "tajunta"]
        self.assertTrue(any("5-HT2A" in e["title"] for e in psychedelic))
        self.assertTrue(any("hait" in e["title"].lower() or "hait" in e["summary"].lower() for e in psychedelic))

    def test_soundboard_is_distinct_from_research(self):
        html = self.get_html()
        self.assertIn('id="hellvoice-style"', html)
        self.assertIn('id="hellvoice-intensity"', html)
        self.assertIn('id="hellvoice-chaos"', html)
        self.assertIn('data-hellfx="chorus72"', html)
        for effect in ["witch", "snort", "squeak", "bones", "heckle"]:
            self.assertIn('id="' + effect + '"', html)
        voice = self.get_static("noki-hellvoice.js").text
        self.assertIn("NokiHellvoice", voice)
        self.assertIn("case \"chorus72\"", voice)
        self.assertIn("for(let ring=0;ring<9;ring++)", voice)
        self.assertIn("for(let seat=0;seat<8;seat++)", voice)
        self.assertIn("speechSynthesis", voice)
        self.assertIn("createDynamicsCompressor", voice)
        self.assertIn("phonetics", voice)
        self.assertNotIn("getUserMedia", voice)

    def test_mimic_and_consented_chat_controls(self):
        html = self.get_html()
        for id_ in ["listen","mimic","talk-engine","engine-enable","engine-source","engine-clear","stop"]:
            self.assertIn('id="' + id_ + '"', html)
        self.assertIn("getUserMedia", html)
        self.assertIn("MediaRecorder", html)
        self.assertIn("decodeAudioData", html)
        self.assertIn("noiseSuppression:false", html)
        self.assertIn("recorder.stop();}},4000)", html)
        self.assertIn('fetch("/api/clone-chat/status"', html)
        self.assertIn('fetch("/api/clone-chat/respond"', html)
        self.assertIn('mode:"bounded"', html)
        self.assertIn('kloneController.abort()', html)
        self.assertIn('if(!document.getElementById("engine-enable").checked)', html)
        self.assertIn("kloneHistory.slice(-12)", html)
        self.assertIn("AbortError", html)

    def test_local_only_code_and_safe_rendering(self):
        html = self.get_html()
        self.assertIn('<script src="/static/noki-hellvoice.js"></script>', html)
        self.assertIn('<script src="/static/noki-grimoire.js"></script>', html)
        self.assertIn("Ei kuvien latausta palvelimelle", html)
        self.assertIn('capture="environment"', html)
        self.assertIn("NokiGrimoire.answer", html)
        self.assertNotIn("localStorage", html)
        self.assertNotIn("https://", html)
        knowledge = self.get_static("noki-grimoire.js").text
        self.assertIn('fetch("/static/noki-grimoire.json"', knowledge)
        self.assertIn("textContent", knowledge)
        self.assertIn("noopener noreferrer", knowledge)
        self.assertNotIn("innerHTML", knowledge)
        self.assertNotIn("getUserMedia", knowledge)
        self.assertNotIn('fetch("https:', knowledge)
        self.assertNotIn('fetch("http:', knowledge)


if __name__ == "__main__":
    unittest.main()
