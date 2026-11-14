"""Smoke checks for the opt-in local-first Noki prototype."""
import unittest
from fastapi.testclient import TestClient
from klone.main import create_app


class NokiCompanionTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(create_app())

    def test_noki_page_is_served(self):
        response = self.client.get("/noki")
        self.assertEqual(response.status_code, 200)
        self.assertIn("text/html", response.headers["content-type"])
        self.assertIn('lang="fi"', response.text)
        self.assertIn("Noki", response.text)

    def test_static_path_is_available(self):
        response = self.client.get("/static/noki.html")
        self.assertEqual(response.status_code, 200)
        self.assertIn("Taidelaboratorio", response.text)

    def test_ragged_voice_and_opt_in_mimic_are_present(self):
        html = self.client.get("/noki").text
        self.assertIn('class="syringe syringe-left"', html)
        self.assertIn('class="syringe syringe-right"', html)
        self.assertIn('id="savage"', html)
        self.assertIn('id="mimic"', html)
        self.assertIn('id="roughness"', html)
        self.assertIn('KRRRÄÄÄ', html)
        self.assertIn('getUserMedia', html)
        self.assertIn('SpeechRecognition', html)
        self.assertIn('MediaRecorder', html)
        self.assertIn('decodeAudioData', html)
        self.assertIn('src.playbackRate.value=.68', html)
        self.assertIn('noiseSuppression:false', html)
        self.assertIn('discardRecord', html)
        self.assertIn('setTimeout(function(){if(recorder.state==="recording"){recorder.stop();}},4000)', html)

    def test_prototype_privacy_and_controls_are_explicit(self):
        html = self.client.get("/noki").text
        self.assertIn('id="listen"', html)
        self.assertIn('id="stop"', html)
        self.assertIn('capture="environment"', html)
        self.assertIn('speechSynthesis', html)
        self.assertIn('createObjectURL', html)
        self.assertIn("Ei kuvien latausta palvelimelle", html)
        self.assertIn('fetch("/api/clone-chat/status"', html)
        self.assertIn('fetch("/api/clone-chat/respond"', html)
        self.assertIn('"mode":"bounded"', html)
        self.assertIn('id="engine-enable"', html)
        self.assertIn('id="engine-source"', html)
        self.assertIn('id="talk-engine"', html)
        self.assertIn('id="witch"', html)
        self.assertIn('id="snort"', html)
        self.assertIn('id="squeak"', html)
        self.assertIn('id="bones"', html)
        self.assertIn('id="heckle"', html)
        self.assertIn("phoneticTTS", html)
        self.assertIn("function sfx(", html)
        self.assertIn("if(!document.getElementById(\"engine-enable\").checked)", html)
        self.assertIn("kloneHistory.slice(-12)", html)
        self.assertIn("Käkänoita", html)
        self.assertNotIn('fetch("https:', html)
        self.assertNotIn('fetch("http:', html)
        self.assertNotIn("localStorage", html)
        self.assertNotIn("<script src=", html)
        self.assertNotIn("https://", html)

if __name__ == "__main__":
    unittest.main()
