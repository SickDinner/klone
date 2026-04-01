from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
from urllib import error as urllib_error
from urllib import request as urllib_request
from typing import Any

from .schemas import (
    CloneChatMessageRecord,
    CloneChatResponseRecord,
    CloneChatStatusRecord,
    DialogueCorpusActivityBucketRecord,
    DialogueCorpusAnalysisRecord,
    DialogueCorpusAnswerRecord,
    DialogueCorpusAnswerSourceRecord,
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
DIALOGUE_CORPUS_ANSWER_VERSION = "2b.7.bounded_dialogue_query_shell"
CLONE_CHAT_VERSION = "2b.8.clone_chat_shell"
FACEBOOK_SOURCE_KIND = "facebook_messenger_export"
CHATGPT_SOURCE_KIND = "chatgpt_conversations_export"
DEFAULT_OPENAI_MODEL = "gpt-5.4"
OPENAI_RESPONSES_URL = "https://api.openai.com/v1/responses"
CHAT_CHANNEL_NAME = "#clone-test-room"
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
QUESTION_NORMALIZE_PATTERN = re.compile(r"[^\w\s\-]+", flags=re.UNICODE)
QUOTED_NAME_PATTERN = re.compile(r"[\"'“”]([^\"'“”]{2,80})[\"'“”]")
CAPITALIZED_NAME_PATTERN = re.compile(
    r"\b[A-ZÅÄÖ][A-Za-zÅÄÖåäö\-]+(?:\s+[A-ZÅÄÖ][A-Za-zÅÄÖåäö\-]+){1,3}\b"
)
TOP_TIES_HINTS = (
    "strongest ties",
    "talk to most",
    "top contacts",
    "top counterparts",
    "closest ties",
    "eniten",
    "vahvimmat siteet",
    "vahvimmat suhteet",
    "kenen kanssa puhun",
    "keiden kanssa puhun",
)
GROUP_HINTS = (
    "group",
    "groups",
    "group thread",
    "group threads",
    "ryhmä",
    "ryhmät",
    "ryhmäkeskustelu",
    "ryhmäkeskustelut",
)
NETWORK_HINTS = (
    "network",
    "verkosto",
    "counterparts",
    "contacts",
    "how many people",
    "kuinka monta ihmistä",
    "kuinka laaja verkosto",
    "direct threads",
    "group threads",
)
TIMELINE_HINTS = (
    "timeline",
    "history",
    "years",
    "aikajana",
    "aktiivisin vuosi",
    "most active year",
    "milloin",
    "ajallinen",
)
STYLE_HINTS = (
    "style",
    "communication style",
    "message style",
    "writing style",
    "viestityyli",
    "kirjoitan",
    "kommunikointi",
    "how do i write",
)
TOPIC_HINTS = (
    "topics",
    "topic",
    "themes",
    "theme",
    "top terms",
    "mistä puhun",
    "aiheet",
    "teemat",
)
SUMMARY_HINTS = (
    "summary",
    "summarize",
    "what does this say",
    "what kind of clone",
    "tiivistä",
    "yhteenveto",
    "mitä tästä voi päätellä",
    "mitä tämä kertoo",
)
SUGGESTED_DIALOGUE_QUERIES = [
    "Keiden kanssa olen puhunut eniten?",
    "Mitkä ovat suurimmat ryhmäkeskusteluni?",
    "Miltä viestityylini näyttää tässä korpuksessa?",
    "Mikä on aikajanan laajuus ja aktiivisin vuosi?",
    "Mitä tiedät Katja Asumasta tämän korpuksen perusteella?",
]
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
    "http",
    "https",
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
    "kans",
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
    "siis",
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
    "viel",
    "vielä",
    "voiko",
    "voisi",
    "voivat",
    "with",
    "without",
    "would",
    "varmaa",
    "your",
}


@dataclass(frozen=True)
class _DiscoveredFacebookSource:
    label: str
    root_path: Path
    message_root: Path
    record_count: int
    status: str


@dataclass(frozen=True)
class _CounterpartLookupResult:
    matched_name: str
    direct_thread_count: int
    sent_message_count: int
    received_message_count: int
    first_message_at: str | None
    last_message_at: str | None
    group_thread_count: int
    group_titles: tuple[str, ...]


class DialogueCorpusService:
    def seam_descriptor(self) -> ServiceSeamRecord:
        return ServiceSeamRecord(
            id="dialogue-corpus-service",
            name="DialogueCorpusService",
            implementation="in_process_local_file_shell",
            status="read_only_analysis_query_and_chat_shell",
            notes=[
                "Analyzes local conversation exports without writing them into memory rows.",
                "Current detectors support extracted Facebook/Messenger exports and ChatGPT conversation export JSON files.",
                "Bounded question answering stays aggregate-only and does not expose raw semantic retrieval.",
                "Clone chat can optionally use OpenAI Responses API when OPENAI_API_KEY is configured, but falls back to bounded local replies.",
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
            ),
            PublicCapabilityRecord(
                id="dialogue.corpus.answer",
                name="Dialogue Corpus Answer",
                category="dialogue_corpus",
                path="/api/dialogue-corpus/answer",
                methods=["POST"],
                read_only=True,
                room_scoped=False,
                status="available",
                description=(
                    "Answer bounded relationship, network, style, and timeline questions from aggregate "
                    "dialogue-corpus evidence without enabling memory writes or raw semantic search."
                ),
                backed_by=["DialogueCorpusService"],
            ),
            PublicCapabilityRecord(
                id="clone.chat.status",
                name="Clone Chat Status",
                category="clone_chat",
                path="/api/clone-chat/status",
                methods=["GET"],
                read_only=True,
                room_scoped=False,
                status="available",
                description=(
                    "Report whether the local clone chat room is ready, which source path will be used by default, "
                    "and whether OpenAI-backed chat is configured."
                ),
                backed_by=["DialogueCorpusService"],
            ),
            PublicCapabilityRecord(
                id="clone.chat.respond",
                name="Clone Chat Respond",
                category="clone_chat",
                path="/api/clone-chat/respond",
                methods=["POST"],
                read_only=True,
                room_scoped=False,
                status="available",
                description=(
                    "Reply in an IRC-style clone test room using bounded dialogue evidence, with optional GPT-5.4 rendering "
                    "when OPENAI_API_KEY is configured."
                ),
                backed_by=["DialogueCorpusService"],
            ),
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

    def answer(
        self,
        *,
        source_path: str,
        question: str,
        owner_name: str | None = None,
    ) -> DialogueCorpusAnswerRecord:
        normalized_question = self._normalize_question(question)
        if not normalized_question:
            raise ValueError("Dialogue corpus question is required.")

        analysis = self.analyze(source_path=source_path, owner_name=owner_name)
        query_kind = self._resolve_query_kind(
            question=question,
            normalized_question=normalized_question,
        )

        if query_kind == "top_counterparts":
            return self._top_counterparts_answer(question=question, analysis=analysis)
        if query_kind == "top_groups":
            return self._top_groups_answer(question=question, analysis=analysis)
        if query_kind == "network":
            return self._network_answer(question=question, analysis=analysis)
        if query_kind == "timeline":
            return self._timeline_answer(question=question, analysis=analysis)
        if query_kind == "style":
            return self._style_answer(question=question, analysis=analysis)
        if query_kind == "topics":
            return self._topics_answer(question=question, analysis=analysis)
        if query_kind == "summary":
            return self._summary_answer(question=question, analysis=analysis)

        name_query = self._extract_name_candidate(question=question, analysis=analysis)
        if name_query and analysis.source_kind == FACEBOOK_SOURCE_KIND:
            lookup = self._lookup_facebook_counterpart(
                analysis=analysis,
                query=name_query,
            )
            if lookup is not None:
                return self._counterpart_lookup_answer(
                    question=question,
                    analysis=analysis,
                    lookup=lookup,
                )

        return self._unsupported_answer(question=question, analysis=analysis)

    def chat_status(self) -> CloneChatStatusRecord:
        return CloneChatStatusRecord(
            default_source_path=self._default_source_path(),
            openai_api_configured=self._openai_api_configured(),
            preferred_model=self._preferred_openai_model(),
            available_modes=["auto", "bounded", "gpt-5.4"],
            channel_name=CHAT_CHANNEL_NAME,
            notes=[
                "The chat room is read-only and grounded in the bounded dialogue-corpus shell.",
                "If OpenAI is not configured, replies stay in local bounded mode without external calls.",
                "Raw semantic retrieval, embeddings, and memory writes stay disabled in this phase.",
            ],
            suggested_queries=list(SUGGESTED_DIALOGUE_QUERIES),
        )

    def chat_reply(
        self,
        *,
        source_path: str,
        message: str,
        history: list[CloneChatMessageRecord] | None = None,
        owner_name: str | None = None,
        mode: str = "auto",
    ) -> CloneChatResponseRecord:
        normalized_message = self._normalize_chat_message(message)
        if not normalized_message:
            raise ValueError("Clone chat message is required.")

        bounded_answer = self.answer(
            source_path=source_path,
            question=normalized_message,
            owner_name=owner_name,
        )

        openai_configured = self._openai_api_configured()
        requested_mode = mode
        backend_mode = "bounded_local"
        llm_call_performed = False
        model: str | None = None
        system_notes: list[str] = []

        if requested_mode == "gpt-5.4" and not openai_configured:
            system_notes.append(
                "GPT-5.4 rendering was requested, but OPENAI_API_KEY is not configured, so the room fell back to bounded local mode."
            )

        if requested_mode in {"auto", "gpt-5.4"} and openai_configured:
            model = self._preferred_openai_model()
            try:
                reply_text = self._render_chat_reply_with_openai(
                    message=normalized_message,
                    bounded_answer=bounded_answer,
                    history=history or [],
                    owner_name=owner_name or bounded_answer.owner_name,
                    model=model,
                )
                backend_mode = "openai_gpt_5_4"
                llm_call_performed = True
            except ValueError as error:
                system_notes.append(f"OpenAI rendering failed, so the room fell back to bounded local mode: {error}")
                reply_text = self._render_local_chat_reply(
                    message=normalized_message,
                    bounded_answer=bounded_answer,
                )
                backend_mode = "bounded_fallback"
                llm_call_performed = False
        else:
            reply_text = self._render_local_chat_reply(
                message=normalized_message,
                bounded_answer=bounded_answer,
            )

        reply = CloneChatMessageRecord(
            role="assistant",
            speaker="klone",
            content=reply_text,
        )
        return CloneChatResponseRecord(
            requested_mode=requested_mode,
            backend_mode=backend_mode,
            model=model,
            openai_api_configured=openai_configured,
            llm_call_performed=llm_call_performed,
            reply=reply,
            answer=bounded_answer,
            system_notes=self._unique_strings(system_notes),
            suggested_queries=list(bounded_answer.suggested_queries),
        )

    def _analyze_facebook_export(
        self,
        *,
        requested_path: Path,
        discovered_sources: list[_DiscoveredFacebookSource],
        selected_source: _DiscoveredFacebookSource,
        owner_name: str | None,
    ) -> DialogueCorpusAnalysisRecord:
        thread_files = self._list_facebook_thread_files(selected_source.message_root)
        participant_thread_counts: Counter[str] = Counter()
        for _, json_path in thread_files:
            payload = self._load_json_file(json_path)
            for participant_name in self._extract_facebook_participants(payload):
                participant_thread_counts[participant_name] += 1

        inferred_owner_name = self._resolve_owner_name(
            participant_thread_counts=participant_thread_counts,
            owner_name=owner_name,
        )
        owner_names = {inferred_owner_name}

        section_thread_counts: Counter[str] = Counter()
        section_message_counts: Counter[str] = Counter()
        unique_counterparts: set[str] = set()
        unique_participants: set[str] = set()
        direct_counterpart_stats: dict[str, dict[str, Any]] = {}
        group_thread_stats: dict[str, dict[str, Any]] = {}
        yearly_message_counts: Counter[str] = Counter()
        yearly_sent_counts: Counter[str] = Counter()
        yearly_received_counts: Counter[str] = Counter()
        yearly_threads: defaultdict[str, set[str]] = defaultdict(set)
        top_term_counts: Counter[str] = Counter()

        thread_count = 0
        direct_thread_count = 0
        group_thread_count = 0
        message_count = 0
        sent_message_count = 0
        received_message_count = 0
        attachment_message_count = 0
        first_timestamp_ms: int | None = None
        last_timestamp_ms: int | None = None

        owner_text_message_count = 0
        owner_total_chars = 0
        owner_question_message_count = 0
        owner_link_message_count = 0
        owner_attachment_message_count = 0

        for section, json_path in thread_files:
            payload = self._load_json_file(json_path)
            thread_id = str(payload.get("thread_path") or f"{section}/{json_path.parent.name}")
            title = self._repair_text(str(payload.get("title") or json_path.parent.name))
            participants = self._extract_facebook_participants(payload)
            participant_names = set(participants)
            unique_participants.update(participant_names)
            counterparts = sorted(name for name in participant_names if name not in owner_names)
            unique_counterparts.update(counterparts)

            messages = payload.get("messages", [])
            if not isinstance(messages, list):
                messages = []

            thread_count += 1
            section_thread_counts[section] += 1
            section_message_counts[section] += len(messages)
            message_count += len(messages)

            thread_first_ms: int | None = None
            thread_last_ms: int | None = None
            thread_sent_count = 0
            thread_received_count = 0
            name_tokens = self._name_tokens(participant_names | owner_names)

            for message in messages:
                if not isinstance(message, dict):
                    continue
                timestamp_ms = self._coerce_int(message.get("timestamp_ms"))
                if timestamp_ms is not None:
                    thread_first_ms = (
                        timestamp_ms if thread_first_ms is None else min(thread_first_ms, timestamp_ms)
                    )
                    thread_last_ms = (
                        timestamp_ms if thread_last_ms is None else max(thread_last_ms, timestamp_ms)
                    )
                    first_timestamp_ms = (
                        timestamp_ms if first_timestamp_ms is None else min(first_timestamp_ms, timestamp_ms)
                    )
                    last_timestamp_ms = (
                        timestamp_ms if last_timestamp_ms is None else max(last_timestamp_ms, timestamp_ms)
                    )
                    year_bucket = self._year_bucket(timestamp_ms)
                    yearly_threads[year_bucket].add(thread_id)
                    yearly_message_counts[year_bucket] += 1

                has_attachment = self._message_has_attachment(message)
                if has_attachment:
                    attachment_message_count += 1

                sender_name = self._repair_text(str(message.get("sender_name") or ""))
                if sender_name in owner_names:
                    thread_sent_count += 1
                    sent_message_count += 1
                    if timestamp_ms is not None:
                        yearly_sent_counts[self._year_bucket(timestamp_ms)] += 1
                    if has_attachment:
                        owner_attachment_message_count += 1
                    content = self._facebook_message_text(message)
                    if content:
                        owner_text_message_count += 1
                        owner_total_chars += len(content)
                        lower_content = content.lower()
                        if "?" in content:
                            owner_question_message_count += 1
                        if "http://" in lower_content or "https://" in lower_content:
                            owner_link_message_count += 1
                        top_term_counts.update(self._extract_terms(content, excluded_tokens=name_tokens))
                else:
                    received_message_count += 1
                    thread_received_count += 1
                    if timestamp_ms is not None:
                        yearly_received_counts[self._year_bucket(timestamp_ms)] += 1

            if len(counterparts) == 1 and len(participant_names) <= 2:
                direct_thread_count += 1
                counterpart_name = counterparts[0]
                stats = direct_counterpart_stats.setdefault(
                    counterpart_name,
                    {
                        "thread_count": 0,
                        "sent_message_count": 0,
                        "received_message_count": 0,
                        "first_message_at": None,
                        "last_message_at": None,
                        "sections": set(),
                    },
                )
                stats["thread_count"] += 1
                stats["sent_message_count"] += thread_sent_count
                stats["received_message_count"] += thread_received_count
                stats["sections"].add(section)
                stats["first_message_at"] = self._min_iso(stats["first_message_at"], thread_first_ms)
                stats["last_message_at"] = self._max_iso(stats["last_message_at"], thread_last_ms)
            elif len(counterparts) >= 2 or len(participant_names) > 2:
                group_thread_count += 1
                group_stats = group_thread_stats.setdefault(
                    thread_id,
                    {
                        "title": title,
                        "participant_count": len(participant_names),
                        "message_count": 0,
                        "first_message_at": None,
                        "last_message_at": None,
                        "sections": set(),
                    },
                )
                group_stats["message_count"] += len(messages)
                group_stats["sections"].add(section)
                group_stats["first_message_at"] = self._min_iso(group_stats["first_message_at"], thread_first_ms)
                group_stats["last_message_at"] = self._max_iso(group_stats["last_message_at"], thread_last_ms)

        section_breakdown = [
            DialogueCorpusSectionRecord(
                section=section,
                thread_count=section_thread_counts[section],
                message_count=section_message_counts[section],
            )
            for section in FACEBOOK_MESSAGE_SECTIONS
            if section_thread_counts[section] or section_message_counts[section]
        ]

        activity_by_year = [
            DialogueCorpusActivityBucketRecord(
                bucket=year,
                thread_count=len(yearly_threads[year]),
                message_count=yearly_message_counts[year],
                sent_message_count=yearly_sent_counts[year],
                received_message_count=yearly_received_counts[year],
            )
            for year in sorted(yearly_message_counts.keys())
        ]

        top_counterparts = sorted(
            (
                DialogueCorpusCounterpartRecord(
                    name=name,
                    thread_count=payload["thread_count"],
                    sent_message_count=payload["sent_message_count"],
                    received_message_count=payload["received_message_count"],
                    interaction_message_count=(
                        payload["sent_message_count"] + payload["received_message_count"]
                    ),
                    first_message_at=payload["first_message_at"],
                    last_message_at=payload["last_message_at"],
                    sections=sorted(payload["sections"]),
                )
                for name, payload in direct_counterpart_stats.items()
            ),
            key=lambda item: (
                item.interaction_message_count,
                item.thread_count,
                item.last_message_at or "",
                item.name.lower(),
            ),
            reverse=True,
        )[:12]

        top_group_threads = sorted(
            (
                DialogueCorpusGroupThreadRecord(
                    title=payload["title"],
                    participant_count=payload["participant_count"],
                    message_count=payload["message_count"],
                    first_message_at=payload["first_message_at"],
                    last_message_at=payload["last_message_at"],
                    sections=sorted(payload["sections"]),
                )
                for payload in group_thread_stats.values()
            ),
            key=lambda item: (item.message_count, item.participant_count, item.last_message_at or ""),
            reverse=True,
        )[:8]

        top_terms = [
            DialogueCorpusTopicRecord(token=token, count=count)
            for token, count in top_term_counts.most_common(12)
        ]

        style_signals = self._build_style_signals(
            sent_message_count=sent_message_count,
            received_message_count=received_message_count,
            owner_text_message_count=owner_text_message_count,
            owner_total_chars=owner_total_chars,
            owner_question_message_count=owner_question_message_count,
            owner_link_message_count=owner_link_message_count,
            owner_attachment_message_count=owner_attachment_message_count,
        )

        most_active_year = (
            max(yearly_message_counts.items(), key=lambda item: (item[1], item[0]))[0]
            if yearly_message_counts
            else None
        )
        top_counterpart_names = ", ".join(
            f"{item.name} ({item.interaction_message_count})" for item in top_counterparts[:3]
        )
        section_lookup = {item.section: item for item in section_breakdown}

        relationship_priors = [
            (
                f"Network spans {len(unique_counterparts)} unique counterparts across "
                f"{direct_thread_count} direct threads and {group_thread_count} group threads."
            )
        ]
        if top_counterpart_names:
            relationship_priors.append(
                f"Strongest direct ties by interaction volume currently surface as {top_counterpart_names}."
            )
        if section_lookup.get("message_requests"):
            relationship_priors.append(
                f"Message requests are present in {section_lookup['message_requests'].thread_count} threads."
            )

        history_priors = []
        if first_timestamp_ms is not None and last_timestamp_ms is not None:
            history_priors.append(
                f"Observed timeline runs from {self._iso_from_ms(first_timestamp_ms)} to {self._iso_from_ms(last_timestamp_ms)}."
            )
        if most_active_year is not None:
            history_priors.append(
                f"Most active year by message volume is {most_active_year} with {yearly_message_counts[most_active_year]} messages."
            )
        if section_lookup.get("e2ee_cutover"):
            history_priors.append(
                f"E2EE cutover continuity is present across {section_lookup['e2ee_cutover'].thread_count} threads."
            )

        notes = [
            "Analysis is read-only and does not write raw Messenger messages into memory tables.",
            f"Owner name resolved as {inferred_owner_name}.",
        ]
        if len(discovered_sources) > 1:
            notes.append(
                f"Selected the richest Facebook export candidate {selected_source.root_path} from {len(discovered_sources)} discovered roots."
            )

        warnings = [
            "Owner-sent counts in top counterpart rankings are attributed only for direct one-to-one threads.",
            "Media attachments are counted structurally; this phase does not OCR, transcribe, or semantically interpret them.",
            "Names, thread titles, and tie strength still require human review before they become durable identity or relationship labels.",
        ]
        if any(source.record_count == 0 for source in discovered_sources):
            warnings.append(
                "Some discovered Facebook export roots look partial or media-only, so the analysis used the most complete JSON-backed root."
            )

        clone_foundation = [
            "This corpus is suitable for seeding relationship-recency, tie-strength, and communication-style priors before any memory writes.",
            "Top direct counterparts can become review candidates for future relationship and provenance layers, not automatic truth labels.",
            "Group-thread coverage can later support social-cluster context once posts, media, and calendar evidence are linked.",
        ]

        return DialogueCorpusAnalysisRecord(
            analysis_version=DIALOGUE_CORPUS_ANALYSIS_VERSION,
            source_kind=FACEBOOK_SOURCE_KIND,
            requested_path=str(requested_path),
            selected_source_path=str(selected_source.root_path),
            owner_name=inferred_owner_name,
            recommended_room_id="intimate",
            recommended_classification_level="intimate",
            read_only=True,
            thread_count=thread_count,
            direct_thread_count=direct_thread_count,
            group_thread_count=group_thread_count,
            counterpart_count=len(unique_counterparts),
            unique_participant_count=len(unique_participants),
            message_count=message_count,
            sent_message_count=sent_message_count,
            received_message_count=received_message_count,
            attachment_message_count=attachment_message_count,
            first_message_at=self._iso_from_ms(first_timestamp_ms),
            last_message_at=self._iso_from_ms(last_timestamp_ms),
            detected_sources=[
                DialogueCorpusSourceRecord(
                    label=source.label,
                    path=str(source.root_path),
                    record_count=source.record_count,
                    status=source.status,
                    selected=source.root_path == selected_source.root_path,
                )
                for source in sorted(
                    discovered_sources,
                    key=lambda item: (item.record_count, item.label),
                    reverse=True,
                )
            ],
            section_breakdown=section_breakdown,
            activity_by_year=activity_by_year,
            top_counterparts=top_counterparts,
            top_group_threads=top_group_threads,
            top_terms=top_terms,
            style_signals=style_signals,
            relationship_priors=relationship_priors,
            history_priors=history_priors,
            clone_foundation=clone_foundation,
            notes=notes,
            warnings=warnings,
        )

    def _analyze_chatgpt_export(
        self,
        *,
        requested_path: Path,
        owner_name: str | None,
    ) -> DialogueCorpusAnalysisRecord:
        payload = self._load_json_file(requested_path)
        if not isinstance(payload, list) or not payload:
            raise ValueError("Unsupported dialogue corpus JSON format.")
        if not isinstance(payload[0], dict) or "mapping" not in payload[0]:
            raise ValueError("Unsupported dialogue corpus JSON format.")

        conversation_count = 0
        message_count = 0
        sent_message_count = 0
        received_message_count = 0
        top_term_counts: Counter[str] = Counter()
        yearly_message_counts: Counter[str] = Counter()
        yearly_sent_counts: Counter[str] = Counter()
        yearly_received_counts: Counter[str] = Counter()
        yearly_threads: defaultdict[str, set[str]] = defaultdict(set)
        model_counts: Counter[str] = Counter()
        first_timestamp_s: float | None = None
        last_timestamp_s: float | None = None

        owner_text_message_count = 0
        owner_total_chars = 0
        owner_question_message_count = 0
        owner_link_message_count = 0

        resolved_owner_name = self._repair_text(owner_name.strip()) if owner_name and owner_name.strip() else "user"

        for conversation in payload:
            if not isinstance(conversation, dict):
                continue
            mapping = conversation.get("mapping")
            if not isinstance(mapping, dict):
                continue
            conversation_count += 1
            thread_id = str(conversation.get("conversation_id") or conversation.get("id") or conversation_count)
            for node in mapping.values():
                if not isinstance(node, dict):
                    continue
                message = node.get("message")
                if not isinstance(message, dict):
                    continue
                role = str((message.get("author") or {}).get("role") or "").strip()
                content = self._chatgpt_message_text(message)
                message_count += 1
                timestamp_s = self._coerce_float(message.get("create_time"))
                if timestamp_s is not None:
                    first_timestamp_s = timestamp_s if first_timestamp_s is None else min(first_timestamp_s, timestamp_s)
                    last_timestamp_s = timestamp_s if last_timestamp_s is None else max(last_timestamp_s, timestamp_s)
                    year_bucket = self._year_bucket_from_seconds(timestamp_s)
                    yearly_threads[year_bucket].add(thread_id)
                    yearly_message_counts[year_bucket] += 1
                metadata = message.get("metadata")
                if isinstance(metadata, dict):
                    model_slug = metadata.get("model_slug") or metadata.get("default_model_slug")
                    if isinstance(model_slug, str) and model_slug:
                        model_counts[model_slug] += 1

                if role == "user":
                    sent_message_count += 1
                    if timestamp_s is not None:
                        yearly_sent_counts[self._year_bucket_from_seconds(timestamp_s)] += 1
                    if content:
                        owner_text_message_count += 1
                        owner_total_chars += len(content)
                        lower_content = content.lower()
                        if "?" in content:
                            owner_question_message_count += 1
                        if "http://" in lower_content or "https://" in lower_content:
                            owner_link_message_count += 1
                        top_term_counts.update(self._extract_terms(content, excluded_tokens=set()))
                else:
                    received_message_count += 1
                    if timestamp_s is not None:
                        yearly_received_counts[self._year_bucket_from_seconds(timestamp_s)] += 1

        activity_by_year = [
            DialogueCorpusActivityBucketRecord(
                bucket=year,
                thread_count=len(yearly_threads[year]),
                message_count=yearly_message_counts[year],
                sent_message_count=yearly_sent_counts[year],
                received_message_count=yearly_received_counts[year],
            )
            for year in sorted(yearly_message_counts.keys())
        ]
        style_signals = self._build_style_signals(
            sent_message_count=sent_message_count,
            received_message_count=received_message_count,
            owner_text_message_count=owner_text_message_count,
            owner_total_chars=owner_total_chars,
            owner_question_message_count=owner_question_message_count,
            owner_link_message_count=owner_link_message_count,
            owner_attachment_message_count=0,
        )
        top_terms = [
            DialogueCorpusTopicRecord(token=token, count=count)
            for token, count in top_term_counts.most_common(12)
        ]
        most_common_models = ", ".join(
            f"{model} ({count})" for model, count in model_counts.most_common(3)
        )
        most_active_year = (
            max(yearly_message_counts.items(), key=lambda item: (item[1], item[0]))[0]
            if yearly_message_counts
            else None
        )

        relationship_priors = [
            "This source captures dialogue with ChatGPT, not human-to-human relationship edges.",
            "No real counterpart network can be inferred from this export alone.",
        ]
        history_priors = []
        if first_timestamp_s is not None and last_timestamp_s is not None:
            history_priors.append(
                f"Observed timeline runs from {self._iso_from_seconds(first_timestamp_s)} to {self._iso_from_seconds(last_timestamp_s)}."
            )
        if most_active_year is not None:
            history_priors.append(
                f"Most active year by prompt volume is {most_active_year} with {yearly_message_counts[most_active_year]} messages."
            )
        if most_common_models:
            history_priors.append(f"Most common model traces in this export are {most_common_models}.")

        return DialogueCorpusAnalysisRecord(
            analysis_version=DIALOGUE_CORPUS_ANALYSIS_VERSION,
            source_kind=CHATGPT_SOURCE_KIND,
            requested_path=str(requested_path),
            selected_source_path=str(requested_path),
            owner_name=resolved_owner_name,
            recommended_room_id="intimate",
            recommended_classification_level="intimate",
            read_only=True,
            thread_count=conversation_count,
            direct_thread_count=0,
            group_thread_count=0,
            counterpart_count=0,
            unique_participant_count=1,
            message_count=message_count,
            sent_message_count=sent_message_count,
            received_message_count=received_message_count,
            attachment_message_count=0,
            first_message_at=self._iso_from_seconds(first_timestamp_s),
            last_message_at=self._iso_from_seconds(last_timestamp_s),
            detected_sources=[
                DialogueCorpusSourceRecord(
                    label=requested_path.name,
                    path=str(requested_path),
                    record_count=conversation_count,
                    status="available",
                    selected=True,
                )
            ],
            section_breakdown=[
                DialogueCorpusSectionRecord(
                    section="chatgpt_export",
                    thread_count=conversation_count,
                    message_count=message_count,
                )
            ],
            activity_by_year=activity_by_year,
            top_counterparts=[],
            top_group_threads=[],
            top_terms=top_terms,
            style_signals=style_signals,
            relationship_priors=relationship_priors,
            history_priors=history_priors,
            clone_foundation=[
                "This corpus can seed prompt-style, topic-preference, and self-directed problem-solving priors before any memory writes.",
                "It is not sufficient for relationship-graph construction without real human conversation exports.",
                "Cross-linking with Messenger, email, notes, and calendar data is still required for real social history modeling.",
            ],
            notes=[
                "Analysis is read-only and does not write prompt or assistant content into memory tables.",
                f"Owner prompt voice is labeled as {resolved_owner_name}.",
            ],
            warnings=[
                "No human relationship graph is available from a ChatGPT export.",
                "Model counts and prompt topics are heuristic priors, not stable identity or social facts.",
            ],
        )

    def _summary_answer(
        self,
        *,
        question: str,
        analysis: DialogueCorpusAnalysisRecord,
    ) -> DialogueCorpusAnswerRecord:
        top_counterparts = ", ".join(
            f"{item.name} ({item.interaction_message_count})"
            for item in analysis.top_counterparts[:3]
        )
        style_map = self._style_signal_map(analysis)
        average_length = style_map.get("avg_sent_message_length")
        question_ratio = style_map.get("question_ratio")
        source_backed_content = [
            DialogueCorpusAnswerSourceRecord(
                content=(
                    f"Observed corpus spans {analysis.counterpart_count} counterparts across "
                    f"{analysis.direct_thread_count} direct threads and {analysis.group_thread_count} group threads."
                ),
                source_refs=["dialogue.relationship_priors", "dialogue.thread_counts"],
            )
        ]
        if top_counterparts:
            source_backed_content.append(
                DialogueCorpusAnswerSourceRecord(
                    content=f"Strongest direct ties currently surface as {top_counterparts}.",
                    source_refs=["dialogue.top_counterparts"],
                )
            )
        if analysis.first_message_at and analysis.last_message_at:
            source_backed_content.append(
                DialogueCorpusAnswerSourceRecord(
                    content=(
                        f"Observed timeline runs from {analysis.first_message_at} to {analysis.last_message_at}."
                    ),
                    source_refs=["dialogue.history_priors", "dialogue.activity_by_year"],
                )
            )
        if average_length and question_ratio:
            source_backed_content.append(
                DialogueCorpusAnswerSourceRecord(
                    content=(
                        f"Owner-sent style signals include average message length {average_length.value} {average_length.unit} "
                        f"and question ratio {question_ratio.value} {question_ratio.unit}."
                    ),
                    source_refs=["dialogue.style_signals"],
                )
            )
        return self._finalize_answer(
            question=question,
            query_kind="summary",
            analysis=analysis,
            supported=True,
            source_backed_content=source_backed_content,
            derived_explanation=(
                "This corpus is already useful for early clone priors around tie strength, recency, network shape, "
                "and communication style, but it is still aggregate-only and not a full semantic memory layer."
            ),
            uncertainty=[
                "Tie strength is still a bounded heuristic based on interaction volume, not a durable relationship truth label."
            ],
        )

    def _top_counterparts_answer(
        self,
        *,
        question: str,
        analysis: DialogueCorpusAnalysisRecord,
    ) -> DialogueCorpusAnswerRecord:
        if not analysis.top_counterparts:
            return self._unsupported_answer(
                question=question,
                analysis=analysis,
                extra_limitations=[
                    "This source does not currently expose direct human counterpart rankings."
                ],
            )
        source_backed_content = [
            DialogueCorpusAnswerSourceRecord(
                content=(
                    f"{item.name}: {item.interaction_message_count} direct-thread messages across "
                    f"{item.thread_count} thread(s) from {item.first_message_at or 'unknown'} "
                    f"to {item.last_message_at or 'unknown'}."
                ),
                source_refs=["dialogue.top_counterparts"],
            )
            for item in analysis.top_counterparts[:5]
        ]
        return self._finalize_answer(
            question=question,
            query_kind="top_counterparts",
            analysis=analysis,
            supported=True,
            source_backed_content=source_backed_content,
            derived_explanation=(
                "This ranking is bounded to one-to-one thread interaction counts only. It does not yet score closeness, "
                "sentiment, reciprocity quality, or topic depth."
            ),
            uncertainty=[
                "Group-thread relationships and offline closeness are not folded into this direct-tie ranking."
            ],
        )

    def _top_groups_answer(
        self,
        *,
        question: str,
        analysis: DialogueCorpusAnalysisRecord,
    ) -> DialogueCorpusAnswerRecord:
        if not analysis.top_group_threads:
            return self._unsupported_answer(
                question=question,
                analysis=analysis,
                extra_limitations=[
                    "This source does not currently expose group-thread rankings."
                ],
            )
        source_backed_content = [
            DialogueCorpusAnswerSourceRecord(
                content=(
                    f"{item.title}: {item.message_count} messages, {item.participant_count} participants, "
                    f"timeline {item.first_message_at or 'unknown'} to {item.last_message_at or 'unknown'}."
                ),
                source_refs=["dialogue.top_group_threads"],
            )
            for item in analysis.top_group_threads[:5]
        ]
        return self._finalize_answer(
            question=question,
            query_kind="top_groups",
            analysis=analysis,
            supported=True,
            source_backed_content=source_backed_content,
            derived_explanation=(
                "This is a bounded ranking of the largest visible group threads by message volume. It helps seed social-cluster "
                "priors without collapsing them into durable group identity claims."
            ),
            uncertainty=[],
        )

    def _network_answer(
        self,
        *,
        question: str,
        analysis: DialogueCorpusAnalysisRecord,
    ) -> DialogueCorpusAnswerRecord:
        section_map = {item.section: item for item in analysis.section_breakdown}
        source_backed_content = [
            DialogueCorpusAnswerSourceRecord(
                content=(
                    f"The visible network spans {analysis.counterpart_count} counterparts and "
                    f"{analysis.unique_participant_count} unique participants across {analysis.thread_count} threads."
                ),
                source_refs=["dialogue.relationship_priors", "dialogue.thread_counts"],
            ),
            DialogueCorpusAnswerSourceRecord(
                content=(
                    f"Thread mix is {analysis.direct_thread_count} direct threads and {analysis.group_thread_count} group threads."
                ),
                source_refs=["dialogue.thread_counts"],
            ),
        ]
        if "message_requests" in section_map:
            source_backed_content.append(
                DialogueCorpusAnswerSourceRecord(
                    content=(
                        f"Message requests are present in {section_map['message_requests'].thread_count} thread(s)."
                    ),
                    source_refs=["dialogue.section_breakdown"],
                )
            )
        return self._finalize_answer(
            question=question,
            query_kind="network",
            analysis=analysis,
            supported=True,
            source_backed_content=source_backed_content,
            derived_explanation=(
                "This answers the visible network shape from export structure only. It is a good first step for relationship "
                "coverage, but not yet a reviewed social graph."
            ),
            uncertainty=[],
        )

    def _timeline_answer(
        self,
        *,
        question: str,
        analysis: DialogueCorpusAnalysisRecord,
    ) -> DialogueCorpusAnswerRecord:
        source_backed_content: list[DialogueCorpusAnswerSourceRecord] = []
        if analysis.first_message_at and analysis.last_message_at:
            source_backed_content.append(
                DialogueCorpusAnswerSourceRecord(
                    content=(
                        f"Observed timeline runs from {analysis.first_message_at} to {analysis.last_message_at}."
                    ),
                    source_refs=["dialogue.history_priors"],
                )
            )
        for item in sorted(
            analysis.activity_by_year,
            key=lambda bucket: (bucket.message_count, bucket.bucket),
            reverse=True,
        )[:3]:
            source_backed_content.append(
                DialogueCorpusAnswerSourceRecord(
                    content=(
                        f"{item.bucket}: {item.message_count} messages across {item.thread_count} threads "
                        f"({item.sent_message_count} sent / {item.received_message_count} received)."
                    ),
                    source_refs=["dialogue.activity_by_year"],
                )
            )
        return self._finalize_answer(
            question=question,
            query_kind="timeline",
            analysis=analysis,
            supported=bool(source_backed_content),
            source_backed_content=source_backed_content,
            derived_explanation=(
                "Timeline answers are bounded to the timestamps present in this export and do not yet cross-link with calendar, "
                "notes, or media evidence."
                if source_backed_content
                else None
            ),
            uncertainty=[],
        )

    def _style_answer(
        self,
        *,
        question: str,
        analysis: DialogueCorpusAnalysisRecord,
    ) -> DialogueCorpusAnswerRecord:
        if not analysis.style_signals:
            return self._unsupported_answer(
                question=question,
                analysis=analysis,
                extra_limitations=[
                    "This source does not currently expose owner-side style signals."
                ],
            )
        source_backed_content = [
            DialogueCorpusAnswerSourceRecord(
                content=f"{item.label}: {item.value} {item.unit}. {item.summary}",
                source_refs=["dialogue.style_signals"],
            )
            for item in analysis.style_signals
        ]
        return self._finalize_answer(
            question=question,
            query_kind="style",
            analysis=analysis,
            supported=True,
            source_backed_content=source_backed_content,
            derived_explanation=(
                "These style signals are aggregate heuristics from owner-sent text only. They are useful for clone voice priors, "
                "but not yet a full stylistic imitation layer."
            ),
            uncertainty=[
                "Attachment-heavy communication is counted structurally and not semantically interpreted."
            ],
        )

    def _topics_answer(
        self,
        *,
        question: str,
        analysis: DialogueCorpusAnalysisRecord,
    ) -> DialogueCorpusAnswerRecord:
        if not analysis.top_terms:
            return self._unsupported_answer(
                question=question,
                analysis=analysis,
                extra_limitations=[
                    "This source does not currently expose bounded top-term signals."
                ],
            )
        source_backed_content = [
            DialogueCorpusAnswerSourceRecord(
                content=(
                    "Top bounded terms currently surface as "
                    + ", ".join(f"{item.token} ({item.count})" for item in analysis.top_terms[:8])
                    + "."
                ),
                source_refs=["dialogue.top_terms"],
            )
        ]
        return self._finalize_answer(
            question=question,
            query_kind="topics",
            analysis=analysis,
            supported=True,
            source_backed_content=source_backed_content,
            derived_explanation=(
                "These topic hints come from token frequency only after stopword filtering. They are not semantic clustering and "
                "should be treated as weak topical priors."
            ),
            uncertainty=[],
        )

    def _counterpart_lookup_answer(
        self,
        *,
        question: str,
        analysis: DialogueCorpusAnalysisRecord,
        lookup: _CounterpartLookupResult,
    ) -> DialogueCorpusAnswerRecord:
        interaction_count = lookup.sent_message_count + lookup.received_message_count
        source_backed_content = [
            DialogueCorpusAnswerSourceRecord(
                content=(
                    f"{lookup.matched_name} appears in {lookup.direct_thread_count} direct thread(s) with "
                    f"{interaction_count} bounded direct messages "
                    f"({lookup.sent_message_count} sent / {lookup.received_message_count} received) "
                    f"from {lookup.first_message_at or 'unknown'} to {lookup.last_message_at or 'unknown'}."
                ),
                source_refs=["facebook.direct_counterpart_lookup"],
            )
        ]
        if lookup.group_thread_count:
            titles = ", ".join(lookup.group_titles[:3])
            source_backed_content.append(
                DialogueCorpusAnswerSourceRecord(
                    content=(
                        f"The same name also appears in {lookup.group_thread_count} group thread(s), including {titles}."
                    ),
                    source_refs=["facebook.group_counterpart_lookup"],
                )
            )
        return self._finalize_answer(
            question=question,
            query_kind="counterpart_lookup",
            analysis=analysis,
            supported=True,
            source_backed_content=source_backed_content,
            derived_explanation=(
                "This is a bounded relationship lookup from thread membership and direct-thread counts only. It does not yet "
                "summarize the meaning, sentiment, or story arc of the relationship."
            ),
            uncertainty=[
                "If multiple people share similar names outside the matched result, they are not fused automatically."
            ],
        )

    def _unsupported_answer(
        self,
        *,
        question: str,
        analysis: DialogueCorpusAnalysisRecord,
        extra_limitations: list[str] | None = None,
    ) -> DialogueCorpusAnswerRecord:
        limitations = self._basic_limitations(analysis)
        limitations.append(
            "Supported bounded queries currently cover summary, top ties, top groups, network shape, timeline, style, topics, and named counterpart lookups."
        )
        if extra_limitations:
            limitations.extend(extra_limitations)
        return self._finalize_answer(
            question=question,
            query_kind="unsupported",
            analysis=analysis,
            supported=False,
            source_backed_content=[],
            derived_explanation=None,
            uncertainty=[],
            extra_limitations=limitations,
        )

    def _finalize_answer(
        self,
        *,
        question: str,
        query_kind: str,
        analysis: DialogueCorpusAnalysisRecord,
        supported: bool,
        source_backed_content: list[DialogueCorpusAnswerSourceRecord],
        derived_explanation: str | None,
        uncertainty: list[str],
        extra_limitations: list[str] | None = None,
    ) -> DialogueCorpusAnswerRecord:
        limitations = self._basic_limitations(analysis)
        if extra_limitations:
            limitations.extend(extra_limitations)
        return DialogueCorpusAnswerRecord(
            answer_version=DIALOGUE_CORPUS_ANSWER_VERSION,
            analysis_version=analysis.analysis_version,
            source_kind=analysis.source_kind,
            requested_path=analysis.requested_path,
            selected_source_path=analysis.selected_source_path,
            owner_name=analysis.owner_name,
            question=question.strip(),
            query_kind=query_kind,
            supported=supported,
            read_only=True,
            source_backed_content=source_backed_content,
            derived_explanation=derived_explanation,
            uncertainty=self._unique_strings(uncertainty),
            limitations=self._unique_strings(limitations),
            suggested_queries=list(SUGGESTED_DIALOGUE_QUERIES),
        )

    def _resolve_query_kind(self, *, question: str, normalized_question: str) -> str:
        if self._contains_hint(normalized_question, TOP_TIES_HINTS):
            return "top_counterparts"
        if self._contains_hint(normalized_question, GROUP_HINTS):
            return "top_groups"
        if self._contains_hint(normalized_question, NETWORK_HINTS):
            return "network"
        if self._contains_hint(normalized_question, TIMELINE_HINTS):
            return "timeline"
        if self._contains_hint(normalized_question, STYLE_HINTS):
            return "style"
        if self._contains_hint(normalized_question, TOPIC_HINTS):
            return "topics"
        if self._contains_hint(normalized_question, SUMMARY_HINTS):
            return "summary"
        return "unclassified"

    def _extract_name_candidate(
        self,
        *,
        question: str,
        analysis: DialogueCorpusAnalysisRecord,
    ) -> str | None:
        repaired_question = self._repair_text(question)
        quoted_match = QUOTED_NAME_PATTERN.search(repaired_question)
        if quoted_match:
            return quoted_match.group(1).strip()

        normalized_question = self._normalize_lookup_text(repaired_question)
        for item in analysis.top_counterparts:
            candidate = self._normalize_lookup_text(item.name)
            if candidate and candidate in normalized_question:
                return item.name

        candidate_names = [
            match.group(0).strip()
            for match in CAPITALIZED_NAME_PATTERN.finditer(repaired_question)
            if self._normalize_lookup_text(match.group(0)) != self._normalize_lookup_text(analysis.owner_name)
        ]
        if not candidate_names:
            return None
        candidate_names.sort(key=lambda item: (len(item.split()), len(item)), reverse=True)
        return candidate_names[0]

    def _lookup_facebook_counterpart(
        self,
        *,
        analysis: DialogueCorpusAnalysisRecord,
        query: str,
    ) -> _CounterpartLookupResult | None:
        source = self._facebook_source_from_path(Path(analysis.selected_source_path))
        if source is None:
            return None

        normalized_query = self._normalize_lookup_text(query)
        if not normalized_query:
            return None

        owner_normalized = self._normalize_lookup_text(analysis.owner_name)
        direct_matches: dict[str, dict[str, Any]] = {}
        direct_scores: dict[str, int] = {}
        group_titles: Counter[str] = Counter()

        for _, json_path in self._list_facebook_thread_files(source.message_root):
            payload = self._load_json_file(json_path)
            participants = self._extract_facebook_participants(payload)
            counterpart_names = [
                name
                for name in participants
                if self._normalize_lookup_text(name) != owner_normalized
            ]
            if not counterpart_names:
                continue

            matched_counterparts = [
                name
                for name in counterpart_names
                if self._name_query_score(name, normalized_query) > 0
            ]
            title = self._repair_text(str(payload.get("title") or json_path.parent.name))
            if len(counterpart_names) > 1 and matched_counterparts:
                group_titles[title] += 1

            if len(counterpart_names) != 1:
                continue
            counterpart_name = counterpart_names[0]
            score = self._name_query_score(counterpart_name, normalized_query)
            if score <= 0:
                continue

            messages = payload.get("messages", [])
            if not isinstance(messages, list):
                messages = []

            first_timestamp_ms: int | None = None
            last_timestamp_ms: int | None = None
            sent_message_count = 0
            received_message_count = 0
            for message in messages:
                if not isinstance(message, dict):
                    continue
                timestamp_ms = self._coerce_int(message.get("timestamp_ms"))
                if timestamp_ms is not None:
                    first_timestamp_ms = (
                        timestamp_ms if first_timestamp_ms is None else min(first_timestamp_ms, timestamp_ms)
                    )
                    last_timestamp_ms = (
                        timestamp_ms if last_timestamp_ms is None else max(last_timestamp_ms, timestamp_ms)
                    )
                sender_name = self._repair_text(str(message.get("sender_name") or ""))
                if self._normalize_lookup_text(sender_name) == owner_normalized:
                    sent_message_count += 1
                else:
                    received_message_count += 1

            stats = direct_matches.setdefault(
                counterpart_name,
                {
                    "direct_thread_count": 0,
                    "sent_message_count": 0,
                    "received_message_count": 0,
                    "first_message_at": None,
                    "last_message_at": None,
                },
            )
            stats["direct_thread_count"] += 1
            stats["sent_message_count"] += sent_message_count
            stats["received_message_count"] += received_message_count
            stats["first_message_at"] = self._min_iso(stats["first_message_at"], first_timestamp_ms)
            stats["last_message_at"] = self._max_iso(stats["last_message_at"], last_timestamp_ms)
            direct_scores[counterpart_name] = max(score, direct_scores.get(counterpart_name, 0))

        if direct_scores:
            top_score = max(direct_scores.values())
            matched_names = sorted(
                name for name, score in direct_scores.items() if score == top_score
            )
            if len(matched_names) == 1:
                matched_name = matched_names[0]
                stats = direct_matches[matched_name]
                return _CounterpartLookupResult(
                    matched_name=matched_name,
                    direct_thread_count=stats["direct_thread_count"],
                    sent_message_count=stats["sent_message_count"],
                    received_message_count=stats["received_message_count"],
                    first_message_at=stats["first_message_at"],
                    last_message_at=stats["last_message_at"],
                    group_thread_count=len(group_titles),
                    group_titles=tuple(title for title, _ in group_titles.most_common(5)),
                )
        return None

    @staticmethod
    def _normalize_question(question: str) -> str:
        repaired = DialogueCorpusService._repair_text(question)
        normalized = QUESTION_NORMALIZE_PATTERN.sub(" ", repaired.casefold())
        return " ".join(normalized.split())

    @staticmethod
    def _normalize_lookup_text(value: str) -> str:
        normalized = QUESTION_NORMALIZE_PATTERN.sub(" ", DialogueCorpusService._repair_text(value).casefold())
        return " ".join(normalized.split())

    @staticmethod
    def _contains_hint(normalized_question: str, hints: tuple[str, ...]) -> bool:
        return any(DialogueCorpusService._normalize_question(hint) in normalized_question for hint in hints)

    @staticmethod
    def _name_query_score(candidate_name: str, normalized_query: str) -> int:
        candidate = DialogueCorpusService._normalize_lookup_text(candidate_name)
        if not candidate or not normalized_query:
            return 0
        if candidate == normalized_query:
            return 3
        candidate_tokens = candidate.split()
        query_tokens = normalized_query.split()
        if query_tokens and all(
            any(
                query_token == candidate_token
                or query_token in candidate_token
                or candidate_token in query_token
                for candidate_token in candidate_tokens
            )
            for query_token in query_tokens
        ):
            return 2 if len(query_tokens) >= 2 else 1
        if normalized_query in candidate or candidate in normalized_query:
            return 1
        return 0

    @staticmethod
    def _style_signal_map(
        analysis: DialogueCorpusAnalysisRecord,
    ) -> dict[str, DialogueCorpusStyleSignalRecord]:
        return {item.key: item for item in analysis.style_signals}

    @staticmethod
    def _unique_strings(items: list[str]) -> list[str]:
        ordered: list[str] = []
        seen: set[str] = set()
        for item in items:
            normalized = item.strip()
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            ordered.append(normalized)
        return ordered

    def _basic_limitations(self, analysis: DialogueCorpusAnalysisRecord) -> list[str]:
        return self._unique_strings(
            list(analysis.warnings)
            + [
                "This answer path is read-only and aggregate-only.",
                "No raw message semantic retrieval, embeddings, sentiment scoring, or psychological inference is enabled in this phase.",
                "Relationship conclusions still require human review before they become durable labels or training truth.",
            ]
        )

    def _default_source_path(self) -> str | None:
        configured = os.environ.get("KLONE_DIALOGUE_SOURCE")
        if configured:
            return configured
        default_path = Path("C:/META")
        if default_path.exists():
            return str(default_path)
        return None

    def _preferred_openai_model(self) -> str:
        return os.environ.get("KLONE_OPENAI_MODEL", DEFAULT_OPENAI_MODEL).strip() or DEFAULT_OPENAI_MODEL

    def _openai_api_configured(self) -> bool:
        return bool(os.environ.get("OPENAI_API_KEY", "").strip())

    def _normalize_chat_message(self, message: str) -> str:
        repaired = self._repair_text(message)
        normalized = repaired.strip()
        if normalized.startswith("/klone "):
            normalized = normalized[len("/klone ") :].strip()
        return normalized

    def _render_local_chat_reply(
        self,
        *,
        message: str,
        bounded_answer: DialogueCorpusAnswerRecord,
    ) -> str:
        if not bounded_answer.supported:
            suggestions = "\n".join(f"- {item}" for item in bounded_answer.suggested_queries[:4])
            limitations = "\n".join(f"- {item}" for item in bounded_answer.limitations[:3])
            return (
                "En pysty vastaamaan tuohon rehellisesti tämän nykyisen bounded-korpuksen perusteella.\n\n"
                f"Kysymys oli: {message}\n\n"
                "Tämän vaiheen rajat ovat:\n"
                f"{limitations}\n\n"
                "Kokeile mieluummin jotain näistä:\n"
                f"{suggestions}"
            )

        evidence_lines = "\n".join(
            f"- {item.content}" for item in bounded_answer.source_backed_content[:4]
        )
        limitation_line = bounded_answer.limitations[0] if bounded_answer.limitations else ""
        explanation_map = {
            "top_counterparts": "Tämän korpuksen perusteella vahvimmat suorat siteet näyttävät tällä hetkellä tältä:",
            "top_groups": "Tämän korpuksen perusteella suurimmat näkyvät ryhmäkeskustelut ovat nämä:",
            "network": "Tämän korpuksen perusteella verkoston muoto näyttää tältä:",
            "timeline": "Tämän korpuksen perusteella aikajana näyttää tältä:",
            "style": "Tämän korpuksen perusteella viestityylissäsi näkyy ainakin tämä:",
            "topics": "Tämän korpuksen perusteella esiin nousevia aihevihjeitä ovat nämä:",
            "summary": "Tämän korpuksen perusteella pystyn sanomaan tämän:",
            "counterpart_lookup": "Tämän korpuksen perusteella kyseisestä ihmisestä näkyy ainakin tämä:",
        }
        explanation = explanation_map.get(
            bounded_answer.query_kind,
            "Tämän korpuksen perusteella pystyn sanomaan tämän:",
        )
        rendered = [
            explanation,
            "",
            evidence_lines,
        ]
        if bounded_answer.uncertainty:
            rendered.extend(
                [
                    "",
                    "Epävarmuus:",
                    "\n".join(f"- {item}" for item in bounded_answer.uncertainty[:2]),
                ]
            )
        if limitation_line:
            rendered.extend(["", f"Raja: {limitation_line}"])
        return "\n".join(part for part in rendered if part)

    def _render_chat_reply_with_openai(
        self,
        *,
        message: str,
        bounded_answer: DialogueCorpusAnswerRecord,
        history: list[CloneChatMessageRecord],
        owner_name: str,
        model: str,
    ) -> str:
        api_key = os.environ.get("OPENAI_API_KEY", "").strip()
        if not api_key:
            raise ValueError("OPENAI_API_KEY is not configured.")

        input_messages = [
            {
                "role": "developer",
                "content": [
                    {
                        "type": "input_text",
                        "text": self._openai_developer_prompt(owner_name=owner_name),
                    }
                ],
            }
        ]
        for item in history[-6:]:
            if item.role not in {"user", "assistant"}:
                continue
            input_messages.append(
                {
                    "role": item.role,
                    "content": [{"type": "input_text", "text": item.content[:3000]}],
                }
            )
        input_messages.append(
            {
                "role": "user",
                "content": [
                    {
                        "type": "input_text",
                        "text": self._openai_user_prompt(message=message, bounded_answer=bounded_answer),
                    }
                ],
            }
        )

        payload = {
            "model": model,
            "reasoning": {"effort": "medium"},
            "input": input_messages,
        }
        response_payload = self._call_openai_responses_api(api_key=api_key, payload=payload)
        output_text = self._extract_openai_text(response_payload)
        if not output_text:
            raise ValueError("OpenAI response did not contain assistant text.")
        return output_text.strip()

    @staticmethod
    def _openai_developer_prompt(*, owner_name: str) -> str:
        return (
            "You are Klone, an experimental IRC-style clone test interface. "
            f"The owner identity label is {owner_name}. "
            "You must answer only from the bounded evidence package that follows. "
            "Do not invent raw message quotes, hidden motives, diagnoses, sentiment labels, or unsupported social claims. "
            "If the bounded answer says the question is unsupported, explain that plainly and steer the user toward supported questions. "
            "Keep the tone conversational and human, and reply in the same language as the user's latest message."
        )

    @staticmethod
    def _openai_user_prompt(
        *,
        message: str,
        bounded_answer: DialogueCorpusAnswerRecord,
    ) -> str:
        evidence = "\n".join(
            f"- {item.content} | refs: {', '.join(item.source_refs)}"
            for item in bounded_answer.source_backed_content
        ) or "- No source-backed content was available."
        uncertainty = "\n".join(f"- {item}" for item in bounded_answer.uncertainty) or "- none"
        limitations = "\n".join(f"- {item}" for item in bounded_answer.limitations) or "- none"
        suggestions = "\n".join(f"- {item}" for item in bounded_answer.suggested_queries[:5]) or "- none"
        return (
            f"User message:\n{message}\n\n"
            f"Bounded query kind: {bounded_answer.query_kind}\n"
            f"Supported: {bounded_answer.supported}\n"
            f"Derived explanation: {bounded_answer.derived_explanation or 'none'}\n\n"
            f"Source-backed content:\n{evidence}\n\n"
            f"Uncertainty:\n{uncertainty}\n\n"
            f"Limitations:\n{limitations}\n\n"
            f"Suggested follow-up questions:\n{suggestions}\n\n"
            "Reply as Klone in a short, natural chat message grounded only in the evidence above."
        )

    def _call_openai_responses_api(
        self,
        *,
        api_key: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        request = urllib_request.Request(
            OPENAI_RESPONSES_URL,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urllib_request.urlopen(request, timeout=90) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib_error.HTTPError as error:
            detail = error.read().decode("utf-8", errors="replace")
            raise ValueError(f"OpenAI API error {error.code}: {detail}") from error
        except urllib_error.URLError as error:
            raise ValueError(f"OpenAI API request failed: {error.reason}") from error

    @staticmethod
    def _extract_openai_text(payload: dict[str, Any]) -> str:
        direct_text = payload.get("output_text")
        if isinstance(direct_text, str) and direct_text.strip():
            return direct_text
        output = payload.get("output")
        if not isinstance(output, list):
            return ""
        parts: list[str] = []
        for item in output:
            if not isinstance(item, dict):
                continue
            content = item.get("content")
            if not isinstance(content, list):
                continue
            for content_part in content:
                if not isinstance(content_part, dict):
                    continue
                if content_part.get("type") == "output_text":
                    text = content_part.get("text")
                    if isinstance(text, str) and text:
                        parts.append(text)
        return "\n".join(parts).strip()

    def _discover_facebook_sources(self, base_path: Path) -> list[_DiscoveredFacebookSource]:
        discovered: dict[str, _DiscoveredFacebookSource] = {}
        for candidate_path in [base_path, *self._direct_child_directories(base_path)]:
            source = self._facebook_source_from_path(candidate_path)
            if source is not None:
                discovered[str(source.root_path)] = source
        return list(discovered.values())

    def _facebook_source_from_path(self, candidate_path: Path) -> _DiscoveredFacebookSource | None:
        if not candidate_path.is_dir():
            return None

        message_root: Path | None = None
        root_path = candidate_path
        direct_root = candidate_path / "your_facebook_activity" / "messages"
        if direct_root.is_dir():
            message_root = direct_root
        elif candidate_path.name == "messages" and any(
            (candidate_path / section).is_dir() for section in FACEBOOK_MESSAGE_SECTIONS
        ):
            message_root = candidate_path
            if candidate_path.parent.name == "your_facebook_activity":
                root_path = candidate_path.parent.parent
        elif any((candidate_path / section).is_dir() for section in FACEBOOK_MESSAGE_SECTIONS):
            message_root = candidate_path

        if message_root is None:
            return None

        record_count = len(self._list_facebook_thread_files(message_root))
        status = "available" if record_count > 0 else "partial_media_only"
        return _DiscoveredFacebookSource(
            label=root_path.name,
            root_path=root_path,
            message_root=message_root,
            record_count=record_count,
            status=status,
        )

    @staticmethod
    def _direct_child_directories(base_path: Path) -> list[Path]:
        if not base_path.is_dir():
            return []
        return [item for item in base_path.iterdir() if item.is_dir()]

    @staticmethod
    def _list_facebook_thread_files(message_root: Path) -> list[tuple[str, Path]]:
        thread_files: list[tuple[str, Path]] = []
        for section in FACEBOOK_MESSAGE_SECTIONS:
            section_root = message_root / section
            if not section_root.is_dir():
                continue
            for json_path in sorted(section_root.rglob("message_*.json")):
                thread_files.append((section, json_path))
        return thread_files

    @staticmethod
    def _extract_facebook_participants(payload: dict[str, Any]) -> list[str]:
        participants = payload.get("participants", [])
        if not isinstance(participants, list):
            return []
        names: list[str] = []
        for participant in participants:
            if not isinstance(participant, dict):
                continue
            name = DialogueCorpusService._repair_text(str(participant.get("name") or ""))
            if name:
                names.append(name)
        return names

    @staticmethod
    def _facebook_message_text(message: dict[str, Any]) -> str:
        content = message.get("content")
        if isinstance(content, str):
            return DialogueCorpusService._repair_text(content)
        return ""

    @staticmethod
    def _chatgpt_message_text(message: dict[str, Any]) -> str:
        content = message.get("content")
        if not isinstance(content, dict):
            return ""
        parts = content.get("parts")
        if isinstance(parts, list):
            return "\n".join(
                DialogueCorpusService._repair_text(str(part))
                for part in parts
                if DialogueCorpusService._repair_text(str(part))
            ).strip()
        text = content.get("text")
        if isinstance(text, str):
            return DialogueCorpusService._repair_text(text)
        return ""

    @staticmethod
    def _message_has_attachment(message: dict[str, Any]) -> bool:
        for field in ATTACHMENT_LIST_FIELDS:
            payload = message.get(field)
            if isinstance(payload, list) and payload:
                return True
        for field in ATTACHMENT_SINGLE_FIELDS:
            if message.get(field):
                return True
        return False

    @staticmethod
    def _resolve_owner_name(
        *,
        participant_thread_counts: Counter[str],
        owner_name: str | None,
    ) -> str:
        normalized_owner = (
            DialogueCorpusService._repair_text(owner_name.strip())
            if owner_name and owner_name.strip()
            else None
        )
        if normalized_owner is not None and normalized_owner in participant_thread_counts:
            return normalized_owner
        if not participant_thread_counts:
            return normalized_owner or "owner"
        highest_count = max(participant_thread_counts.values())
        highest_names = sorted(
            name for name, count in participant_thread_counts.items() if count == highest_count
        )
        return highest_names[0]

    @staticmethod
    def _extract_terms(content: str, *, excluded_tokens: set[str]) -> list[str]:
        terms: list[str] = []
        for token in TOKEN_PATTERN.findall(content.lower()):
            if token in STOPWORDS or token in excluded_tokens:
                continue
            terms.append(token)
        return terms

    @staticmethod
    def _name_tokens(names: set[str]) -> set[str]:
        tokens: set[str] = set()
        for name in names:
            for token in TOKEN_PATTERN.findall(name.lower()):
                tokens.add(token)
        return tokens

    @staticmethod
    def _repair_text(value: str) -> str:
        text = value.strip()
        if not text:
            return ""
        if any(marker in text for marker in ("Ã", "Â", "ð", "�")):
            try:
                repaired = text.encode("latin1").decode("utf-8")
                if repaired:
                    return repaired.strip()
            except UnicodeError:
                return text
        return text

    @staticmethod
    def _build_style_signals(
        *,
        sent_message_count: int,
        received_message_count: int,
        owner_text_message_count: int,
        owner_total_chars: int,
        owner_question_message_count: int,
        owner_link_message_count: int,
        owner_attachment_message_count: int,
    ) -> list[DialogueCorpusStyleSignalRecord]:
        average_length = (
            owner_total_chars / owner_text_message_count if owner_text_message_count else 0.0
        )
        question_ratio = (
            owner_question_message_count / owner_text_message_count * 100.0
            if owner_text_message_count
            else 0.0
        )
        link_ratio = (
            owner_link_message_count / owner_text_message_count * 100.0
            if owner_text_message_count
            else 0.0
        )
        attachment_ratio = (
            owner_attachment_message_count / sent_message_count * 100.0 if sent_message_count else 0.0
        )
        sent_share = (
            sent_message_count / (sent_message_count + received_message_count) * 100.0
            if sent_message_count + received_message_count
            else 0.0
        )

        if average_length >= 180:
            length_summary = "Long-form written turns appear regularly in the owner-sent text."
        elif average_length >= 70:
            length_summary = "Owner-sent text mixes short replies with medium-length explanation."
        else:
            length_summary = "Owner-sent text skews short and bursty in this corpus."

        if question_ratio >= 18:
            question_summary = "The owner often drives exchanges with explicit questions."
        elif question_ratio >= 8:
            question_summary = "Questions are a recurring but not dominant part of the owner voice."
        else:
            question_summary = "Most owner-sent turns are statements, reactions, or directives rather than explicit questions."

        if link_ratio >= 8:
            link_summary = "External links are a visible part of the owner communication style."
        else:
            link_summary = "Links appear only occasionally in the owner-sent text."

        if attachment_ratio >= 15:
            attachment_summary = "Attachments are a significant part of the owner side of the corpus."
        else:
            attachment_summary = "The owner side is mostly text-first at this stage of analysis."

        if sent_share >= 55:
            sent_share_summary = "The corpus currently leans toward owner-initiated or owner-dense exchanges."
        elif sent_share >= 45:
            sent_share_summary = "The corpus looks relatively balanced between sent and received turns."
        else:
            sent_share_summary = "The corpus leans more heavily toward inbound turns than owner output."

        return [
            DialogueCorpusStyleSignalRecord(
                key="avg_sent_message_length",
                label="Average Sent Message Length",
                value=round(average_length, 2),
                unit="chars",
                summary=length_summary,
            ),
            DialogueCorpusStyleSignalRecord(
                key="question_ratio",
                label="Question Ratio",
                value=round(question_ratio, 2),
                unit="percent",
                summary=question_summary,
            ),
            DialogueCorpusStyleSignalRecord(
                key="link_ratio",
                label="Link Ratio",
                value=round(link_ratio, 2),
                unit="percent",
                summary=link_summary,
            ),
            DialogueCorpusStyleSignalRecord(
                key="attachment_send_ratio",
                label="Attachment Send Ratio",
                value=round(attachment_ratio, 2),
                unit="percent",
                summary=attachment_summary,
            ),
            DialogueCorpusStyleSignalRecord(
                key="sent_share",
                label="Sent Share",
                value=round(sent_share, 2),
                unit="percent",
                summary=sent_share_summary,
            ),
        ]

    @staticmethod
    def _coerce_int(value: Any) -> int | None:
        if isinstance(value, bool):
            return None
        if isinstance(value, int):
            return value
        if isinstance(value, float):
            return int(value)
        return None

    @staticmethod
    def _coerce_float(value: Any) -> float | None:
        if isinstance(value, bool):
            return None
        if isinstance(value, (int, float)):
            return float(value)
        return None

    @staticmethod
    def _load_json_file(path: Path) -> Any:
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as error:
            raise ValueError(f"Failed to parse JSON dialogue corpus source: {path}") from error

    @staticmethod
    def _iso_from_ms(value: int | None) -> str | None:
        if value is None:
            return None
        return datetime.fromtimestamp(value / 1000.0, tz=timezone.utc).isoformat().replace("+00:00", "Z")

    @staticmethod
    def _iso_from_seconds(value: float | None) -> str | None:
        if value is None:
            return None
        return datetime.fromtimestamp(value, tz=timezone.utc).isoformat().replace("+00:00", "Z")

    @staticmethod
    def _year_bucket(timestamp_ms: int) -> str:
        return datetime.fromtimestamp(timestamp_ms / 1000.0, tz=timezone.utc).strftime("%Y")

    @staticmethod
    def _year_bucket_from_seconds(timestamp_s: float) -> str:
        return datetime.fromtimestamp(timestamp_s, tz=timezone.utc).strftime("%Y")

    def _min_iso(self, current: str | None, candidate_ms: int | None) -> str | None:
        candidate = self._iso_from_ms(candidate_ms)
        if current is None:
            return candidate
        if candidate is None:
            return current
        return candidate if candidate < current else current

    def _max_iso(self, current: str | None, candidate_ms: int | None) -> str | None:
        candidate = self._iso_from_ms(candidate_ms)
        if current is None:
            return candidate
        if candidate is None:
            return current
        return candidate if candidate > current else current
