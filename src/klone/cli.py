from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys
from typing import Sequence

from .dialogue import DialogueCorpusService
from .schemas import DialogueCorpusAnalysisRecord, DialogueCorpusAnswerRecord


PROJECT_ROOT = Path(__file__).resolve().parents[2]
TRAINING_PLAN_PATH = PROJECT_ROOT / "docs" / "DIALOGUE_CORPUS_NEXT_AND_TRAINING_PLAN.md"


def _default_source_path() -> str | None:
    configured = os.environ.get("KLONE_DIALOGUE_SOURCE")
    if configured:
        return configured
    windows_default = Path("C:/META")
    if windows_default.exists():
        return str(windows_default)
    return None


def _normalize_argv(argv: Sequence[str] | None) -> list[str]:
    normalized = list(argv) if argv is not None else sys.argv[1:]
    if normalized and normalized[0].strip().lower() == "/klone":
        return normalized[1:]
    return normalized


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="klone",
        description=(
            "Query the bounded dialogue-corpus parser over local Messenger or ChatGPT exports "
            "without enabling memory writes."
        ),
    )
    parser.add_argument(
        "question",
        nargs="*",
        help="Question to ask from the dialogue corpus. If omitted, prints the current analysis summary.",
    )
    parser.add_argument(
        "--source",
        default=None,
        help="Source path to an extracted Messenger export root, ChatGPT conversations export JSON, or a parent folder like C:\\META.",
    )
    parser.add_argument(
        "--owner-name",
        default=None,
        help="Optional explicit owner name if automatic resolution should be overridden.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print the raw JSON response instead of the human-readable summary.",
    )
    parser.add_argument(
        "--analyze",
        action="store_true",
        help="Print only the aggregate corpus analysis instead of answering a question.",
    )
    parser.add_argument(
        "--plan",
        action="store_true",
        help="Print the current continuation and training plan document path and contents.",
    )
    return parser


def _print_analysis(analysis: DialogueCorpusAnalysisRecord) -> None:
    print(f"Source: {analysis.selected_source_path}")
    print(f"Kind: {analysis.source_kind}")
    print(f"Owner: {analysis.owner_name}")
    print(
        "Network: "
        f"{analysis.counterpart_count} counterparts, "
        f"{analysis.direct_thread_count} direct threads, "
        f"{analysis.group_thread_count} group threads"
    )
    print(
        "Messages: "
        f"{analysis.message_count} total "
        f"({analysis.sent_message_count} sent / {analysis.received_message_count} received)"
    )
    if analysis.first_message_at and analysis.last_message_at:
        print(f"Timeline: {analysis.first_message_at} -> {analysis.last_message_at}")
    if analysis.top_counterparts:
        print(
            "Top counterparts: "
            + ", ".join(
                f"{item.name} ({item.interaction_message_count})"
                for item in analysis.top_counterparts[:5]
            )
        )
    if analysis.top_group_threads:
        print(
            "Top groups: "
            + ", ".join(
                f"{item.title} ({item.message_count})"
                for item in analysis.top_group_threads[:3]
            )
        )


def _print_answer(answer: DialogueCorpusAnswerRecord) -> None:
    print(f"Question: {answer.question}")
    print(f"Supported: {'yes' if answer.supported else 'no'}")
    print(f"Query kind: {answer.query_kind}")
    print(f"Source: {answer.selected_source_path}")
    if answer.derived_explanation:
        print()
        print(answer.derived_explanation)
    if answer.source_backed_content:
        print()
        print("Evidence:")
        for item in answer.source_backed_content:
            print(f"- {item.content}")
    if answer.uncertainty:
        print()
        print("Uncertainty:")
        for item in answer.uncertainty:
            print(f"- {item}")
    if answer.limitations:
        print()
        print("Limitations:")
        for item in answer.limitations:
            print(f"- {item}")
    if not answer.supported and answer.suggested_queries:
        print()
        print("Try one of these:")
        for item in answer.suggested_queries:
            print(f"- {item}")


def _print_plan() -> int:
    print(f"Plan: {TRAINING_PLAN_PATH}")
    print()
    if not TRAINING_PLAN_PATH.exists():
        print("Training plan document is not present yet.", file=sys.stderr)
        return 1
    print(TRAINING_PLAN_PATH.read_text(encoding="utf-8"))
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(_normalize_argv(argv))

    if args.plan:
        return _print_plan()

    source_path = args.source or _default_source_path()
    if not source_path:
        print(
            "No dialogue corpus source path was provided. Use --source or set KLONE_DIALOGUE_SOURCE.",
            file=sys.stderr,
        )
        return 2

    service = DialogueCorpusService()
    try:
        if args.analyze or not args.question:
            analysis = service.analyze(source_path=source_path, owner_name=args.owner_name)
            if args.json:
                print(json.dumps(analysis.model_dump(mode="json"), indent=2, ensure_ascii=False))
            else:
                _print_analysis(analysis)
            return 0

        question = " ".join(args.question).strip()
        answer = service.answer(
            source_path=source_path,
            question=question,
            owner_name=args.owner_name,
        )
        if args.json:
            print(json.dumps(answer.model_dump(mode="json"), indent=2, ensure_ascii=False))
        else:
            _print_answer(answer)
        return 0
    except (FileNotFoundError, ValueError, OSError) as error:
        print(str(error), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
