"""KLONE Knowledge Atlas: 72 curated Wikipedia expertise lanes.

Canonical Council72 member names, IDs and tasks always come from
the existing council catalog; these are PUBLIC source-discovery hints,
not model instructions, credentials or new runtime authority.

Each member gets exactly three core Wikipedia-oriented English
discovery concepts; all share the same underlying article store.
"""
from __future__ import annotations

from .council72 import catalog

# ID -> three deliberately distinct disciplinary entry points.
# These are queries, NOT an assertion that a particular article exists.
ROLE_TOPICS = {
    24: ("Linguistics", "Translation studies", "Sociolinguistics"),
    27: ("Social psychology", "Public opinion", "Collective intelligence"),
    30: ("Technical communication", "Readability", "Instructional design"),
    53: ("Conflict resolution", "Negotiation theory", "Epistemic injustice"),
    55: ("Source criticism", "Fact-checking", "Scientific method"),
    70: ("Journalism", "Observation", "Situational awareness"),
    11: ("Ontology (information science)", "Knowledge organization", "Information retrieval"),
    71: ("Pragmatics", "Psycholinguistics", "Interpersonal communication"),

    12: ("Motivation", "Curiosity", "Self-determination theory"),
    16: ("Decision theory", "Multi-objective optimization", "Goal setting"),
    19: ("Cooperation", "Game theory", "Collaborative learning"),
    13: ("Ethics", "Value theory", "Commitment"),
    34: ("Creativity", "Dialectic", "Divergent thinking"),
    37: ("Music theory", "Acoustics", "Aesthetics"),
    47: ("Social network analysis", "Context (linguistics)", "Relational sociology"),
    56: ("Requirements engineering", "User research", "Human-centered design"),

    4: ("Archival science", "Source criticism", "Metadata"),
    3: ("Information retrieval", "Context awareness", "Lost media"),
    8: ("Knowledge graph", "Causal inference", "Association rule learning"),
    7: ("Change detection", "Temporal database", "Event sourcing"),
    29: ("Belief revision", "Paraconsistent logic", "Knowledge representation"),
    46: ("Semantic network", "Ontology engineering", "Taxonomy"),
    54: ("Historiography", "Historical method", "Digital preservation"),
    72: ("Data provenance", "Revision control", "Error correction"),

    26: ("Computational complexity", "Energy efficiency", "Resource allocation"),
    6: ("Memory leak", "Performance engineering", "Resource contention"),
    48: ("Cost-benefit analysis", "Transformation (mathematics)", "Algorithmic efficiency"),
    58: ("Experimental design", "Value of information", "Cost-effectiveness analysis"),
    62: ("Data inventory", "Data catalog", "Information resource"),
    39: ("Dependency graph", "Critical path method", "Software construction"),
    38: ("Operating system scheduling", "Process isolation", "Workload management"),
    33: ("Edge computing", "Distributed computing", "Cloud computing"),

    5: ("Medical diagnosis", "Anomaly detection", "Differential diagnosis"),
    10: ("Circadian rhythm", "Homeostasis", "Stress recovery"),
    17: ("De-escalation", "Emotion regulation", "Conflict management"),
    22: ("Risk perception", "Decision-making under uncertainty", "Courage"),
    14: ("Signal detection theory", "False alarm", "Alert fatigue"),
    35: ("Stress testing", "Resilience engineering", "Failure analysis"),
    63: ("Group conflict", "Disagreement", "Dissent"),
    41: ("Cognitive load", "Rate limiting", "System overload"),

    21: ("Concept formation", "Operational definition", "Variable (mathematics)"),
    36: ("Multimodal learning", "Signal processing", "Sensor fusion"),
    31: ("Hypothesis", "Falsifiability", "Scientific experiment"),
    50: ("Formal logic", "Deductive reasoning", "Logical fallacy"),
    60: ("Prototyping", "Software engineering", "Rapid application development"),
    65: ("Geometry", "Graph theory", "Topology"),
    59: ("Model selection", "Model drift", "Change-point detection"),
    66: ("Abductive reasoning", "Alternative hypothesis", "Causal model"),

    2: ("Input/output", "Type system", "Application security"),
    15: ("Dependency management", "Forecasting", "Systems engineering"),
    18: ("Android (operating system)", "Linux", "Portability (software)"),
    23: ("Incremental development", "Patch (computing)", "Change management"),
    25: ("Fault injection", "Simulation", "Failure mode and effects analysis"),
    42: ("Computer network", "TCP and UDP port", "Service monitoring"),
    43: ("Sandbox (computer security)", "Access control", "Process isolation"),
    49: ("Application programming interface", "Dataflow programming", "Protocol design"),

    28: ("Epistemology", "Verification", "Scientific claim"),
    44: ("Missing data", "Evidence", "Burden of proof"),
    40: ("Data provenance", "Chain of custody", "Scientific reproducibility"),
    52: ("Responsibility assignment matrix", "Role-based access control", "Governance"),
    57: ("Cognitive bias", "Misinformation", "Statistical fallacy"),
    64: ("Regression testing", "Counterfactual reasoning", "Adversarial testing"),
    67: ("Multi-agent system", "Coordination", "Consensus algorithm"),
    69: ("Data integrity", "Cryptographic hash function", "Consistency model"),

    1: ("Information ethics", "Information provenance", "Border security"),
    9: ("Philosophy of mind", "Learning theory", "Theory of meaning"),
    20: ("Autobiographical memory", "History of consciousness", "Long-term memory"),
    32: ("Operations research", "Resource optimization", "Project management"),
    51: ("Affective neuroscience", "Executive functions", "Emotion regulation"),
    61: ("Philosophy of science", "Self-model", "Conceptual model"),
    45: ("Software architecture", "Systems integration", "Cybernetics"),
    68: ("Research ethics", "Accountability", "Evidence-based practice"),
}

# Broad shared education improves cross-ring communication without
# duplicating storage or inventing 72 different independent minds.
SHARED_FOUNDATIONS = (
    "History of science", "Mathematics", "Physics", "Chemistry",
    "Biology", "Ecology", "Geography", "World history",
    "Philosophy", "Economics", "Political science", "Law",
    "Linguistics", "Literature", "Art history", "Medicine",
    "Computer science", "Statistics", "Research methods",
    "Ethics", "Technology", "Anthropology", "Archaeology",
    "Music", "Earth science", "Astronomy", "Genetics",
    "Neuroscience", "Engineering", "Psychology",
    "Logic", "Information science",
)

LANGUAGES = ("fi", "en", "sv", "no", "da", "is", "de", "fr", "es")
TARGET_UNIQUE_ARTICLES = 72_000
PHASES = (2_000, 12_000, 30_000, TARGET_UNIQUE_ARTICLES)


def profiles() -> list[dict]:
    council = catalog()
    ids = {m["id"] for m in council["members"]}
    if ids != set(ROLE_TOPICS) or len(ids) != 72:
        raise ValueError("every canonical Council72 role needs a unique expertise lane")
    result = []
    for member in council["members"]:
        topics = ROLE_TOPICS[member["id"]]
        if len(topics) != 3 or len(set(topics)) != 3:
            raise ValueError("invalid duplicate or missing expertise topics")
        result.append({
            "member_id": member["id"],
            "ring_id": member["ring"],
            "name": member["name"],
            "canonical_task": member["task"],
            "founder": member["founder"],
            "expertise_topics": list(topics),
            "source_languages": list(LANGUAGES),
            "knowledge_access": "public_read_only",
            "memory_write_permission": False,
            "inferred_expertise_from_text": False,
        })
    return sorted(result, key=lambda x: x["member_id"])


def plan() -> dict:
    return {
        "kind": "klone-knowledge-atlas-plan-v1",
        "target_distinct_pages": TARGET_UNIQUE_ARTICLES,
        "phases_distinct_pages": list(PHASES),
        "source": "Wikipedia/Wikimedia; public content only",
        "profiles": profiles(),
        "shared_foundations": list(SHARED_FOUNDATIONS),
        "languages": list(LANGUAGES),
        "total_role_profiles": 72,
        "topic_queries_per_member": 3,
        "topic_queries_total": 216,
        "no_articles_downloaded_by_plan": True,
        "memory_write": False,
        "model_api_requests": 0,
        "scientific_truth_verified": False,
    }
