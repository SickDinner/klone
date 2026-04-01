from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
import re
from typing import Any

from .schemas import (
    DialogueCorpusActivityBucketRecord,
    DialogueCorpusAnalysisRecord,
    DialogueCorpusCounterpartRecord,
    DialogueCorpusGroupThreadRecord,
    DialogueCorpusSourceRecord,
    DialogueCorpusSectionRecord,
    DialogueCorpusStyleSignalRecord,
    DialogueCorpusTopicRecord,
    PublicCapabilityRecord,
    ServiceSeamRecord,
)


DIALOGUE_CORPUS_ANALYSIS_VERSION = "2b.6.read_only_dialogue_corpus_shell"
FACEBOOK_SOURCE_KIND = "facebook_messenger_export"
CHATGPT_SOURCE_KIND = "chatgpt_conversations_export"
FACEBOOK_MESSAGE_SECTIONS = (
    "inbox",
    "archived_threads",
    "filtered_threads",
    "message_requests",
    "e2ee_cutover",
)
ATTACHMENT_LIST_FIELDS = ("photos", "videos", "audio_files", "files", "gifs")
ATTACHMENT_SINGLE_FIELDS = ("sticker", "share")
TOKEN_PATTERN = re.compile(r"[^\W\d_]{4,}", flags=re.UNICODE)
STOPWORDS = {
    "about",
    "again",
    "after",
    "against",
    "aika",
    "aina",
    "alkaa",
    "alla",
    "alle",
    "also",
    "antaa",
    "because",
    "before",
    "being",
    "between",
    "both",
    "chat",
    "could",
    "ehka",
    "eika",
    "ellei",
    "enemman",
    "erittäin",
    "että",
    "from",
    "have",
    "hello",
    "here",
    "hyvin",
    "ihan",
    "into",
    "itse",
    "joka",
    "jokin",
    "joku",
    "jolla",
    "jonka",
    "jotka",
    "jotta",
    "just",
    "kaikki",
    "kanssa",
    "kautta",
    "koko",
    "koska",
    "kuin",
    "kunhan",
    "lähetti",
    "liite",
    "liitteen",
    "message",
    "mihin",
    "mikä",
    "miksi",
    "milla",
    "mitä",
    "miten",
    "mulla",
    "mun",
    "mutta",
    "näitä",
    "näytä",
    "need",
    "niin",
    "niitä",
    "noin",
    "olla",
    "olisi",
    "olivat",
    "only",
    "over",
    "paljon",
    "paremmin",
    "please",
    "pystyy",
    "saada",
    "sama",
    "sent",
    "sille",
    "sitten",
    "some",
    "suoraan",
    "tahan",
    "tai",
    "taas",
    "tama",
    "tätä",
    "tehdä",
    "tekee",
    "than",
    "that",
    "this",
    "tieto",
    "tuoda",
    "tuolla",
    "vaan",
    "vähän",
    "very",
    "vielä",
    "voiko",
    "voisi",
    "voivat",
    "with",
    "without",
    "would",
    "your",
}


@dataclass(frozen=True)
class _DiscoveredFacebookSource:
    label: str
    root_path: Path
    message_root: Path
    record_count: int
    status: str


class DialogueCorpusService:
    def seam_descriptor(self) -> ServiceSeamRecord:
        return ServiceSeamRecord(
            id="dialogue-corpus-service",
            name="DialogueCorpusService",
            implementation="in_process_local_file_shell",
            status="read_only_source_analysis",
            notes=[
                "Analyzes local conversation exports without writing them into memory rows.",
                "Current detectors support extracted Facebook/Messenger exports and ChatGPT conversation export JSON files.",
            ],
        )

    def public_capabilities(self) -> list[PublicCapabilityRecord]:
        return [
            PublicCapabilityRecord(
                id="dialogue.corpus.analyze",
                name="Dialogue Corpus Analyze",
                category="dialogue_corpus",
                path="/api/dialogue-corpus/analyze",
                methods=["POST"],
                read_only=True,
                room_scoped=False,
                status="available",
                description=(
                    "Analyze a local conversation export for relationship, network, style, and history priors "
                    "without writing raw dialogue into memory."
                ),
                backed_by=["DialogueCorpusService"],
            )
        ]

    def analyze(
        self,
        *,
        source_path: str,
        owner_name: str | None = None,
    ) -> DialogueCorpusAnalysisRecord:
        requested_path = Path(source_path).expanduser()
        if not requested_path.exists():
            raise FileNotFoundError(f"Dialogue corpus source path was not found: {requested_path}")

        if requested_path.is_file():
            return self._analyze_chatgpt_export(
                requested_path=requested_path,
                owner_name=owner_name,
            )

        discovered_sources = self._discover_facebook_sources(requested_path)
        if not discovered_sources:
            raise ValueError(
                "Unsupported dialogue corpus source. Provide an extracted Facebook/Messenger export directory "
                "or a ChatGPT conversations export JSON file."
            )
        selected_source = max(discovered_sources, key=lambda item: (item.record_count, item.label))
        if selected_source.record_count <= 0:
            raise ValueError(
                "Facebook export roots were found, but no Messenger JSON thread files were available in them."
            )
        return self._analyze_facebook_export(
            requested_path=requested_path,
            discovered_sources=discovered_sources,
            selected_source=selected_source,
            owner_name=owner_name,
        )
