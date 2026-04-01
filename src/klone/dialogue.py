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
            title = str(payload.get("title") or json_path.parent.name)
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

                sender_name = str(message.get("sender_name") or "").strip()
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

        resolved_owner_name = owner_name.strip() if owner_name and owner_name.strip() else "user"

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
            name = str(participant.get("name") or "").strip()
            if name:
                names.append(name)
        return names

    @staticmethod
    def _facebook_message_text(message: dict[str, Any]) -> str:
        content = message.get("content")
        if isinstance(content, str):
            return content.strip()
        return ""

    @staticmethod
    def _chatgpt_message_text(message: dict[str, Any]) -> str:
        content = message.get("content")
        if not isinstance(content, dict):
            return ""
        parts = content.get("parts")
        if isinstance(parts, list):
            return "\n".join(str(part).strip() for part in parts if str(part).strip()).strip()
        text = content.get("text")
        if isinstance(text, str):
            return text.strip()
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
        normalized_owner = owner_name.strip() if owner_name and owner_name.strip() else None
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
