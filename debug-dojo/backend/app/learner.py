"""
Learner module: Concept mastery tracking, recurring mistake detection,
and adaptive challenge recommendation engine.

Rules:
- 7 Core Concepts: Lists, Loops, Functions, Conditions, Indexing, Strings, Input handling
- Recurring threshold: A tag is recurring once it appears across >= 2 DIFFERENT challenges.
- Mastery updates:
  * Pass with 0 hints: +10 pts (cap 100)
  * Pass with hints: +5 pts (cap 100)
  * Fail / repeated mistake: -3 pts (floor 0)
- Challenge recommendation: Heavily boosts challenges (+45) targeting recurring mistakes and low-mastery concepts.
"""

import json
from pathlib import Path
from typing import Dict, Any, List, Set, Tuple
from .db import get_db_connection

CORE_CONCEPTS = [
    "Lists",
    "Loops",
    "Functions",
    "Conditions",
    "Indexing",
    "Strings",
    "Input handling"
]

CHALLENGES_DIR = Path(__file__).resolve().parent.parent / "challenges"


def load_all_challenges() -> List[Dict[str, Any]]:
    challenges = []
    if CHALLENGES_DIR.exists():
        for f in CHALLENGES_DIR.glob("*.json"):
            try:
                with open(f, "r", encoding="utf-8") as fp:
                    data = json.load(fp)
                    challenges.append(data)
            except Exception:
                pass
    return challenges


def get_learner_history(learner_id: str) -> List[Dict[str, Any]]:
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT id, learner_id, challenge_id, passed, mistake_tags, created_at
            FROM submissions
            WHERE learner_id = ?
            ORDER BY created_at ASC
            """,
            (learner_id,)
        )
        rows = cursor.fetchall()

    history = []
    for r in rows:
        tags = []
        try:
            tags = json.loads(r["mistake_tags"])
        except Exception:
            pass

        history.append({
            "id": r["id"],
            "challenge_id": r["challenge_id"],
            "passed": bool(r["passed"]),
            "mistake_tags": tags,
            "created_at": r["created_at"]
        })
    return history


def get_hints_used_count(submission_id: str) -> int:
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT COUNT(*) as count FROM hints_given WHERE submission_id = ?",
            (submission_id,)
        )
        row = cursor.fetchone()
        return row["count"] if row and row["count"] is not None else 0


def calculate_recurring_mistakes(history: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    A mistake tag is recurring if and only if it appears across at least 2 DIFFERENT challenges.
    """
    mistake_to_challenges: Dict[str, Set[str]] = {}
    mistake_counts: Dict[str, int] = {}

    for sub in history:
        cid = sub["challenge_id"]
        for tag in sub["mistake_tags"]:
            if tag not in mistake_to_challenges:
                mistake_to_challenges[tag] = set()
                mistake_counts[tag] = 0
            mistake_to_challenges[tag].add(cid)
            mistake_counts[tag] += 1

    recurring = []
    for tag, cids in mistake_to_challenges.items():
        if len(cids) >= 2:
            recurring.append({
                "tag": tag,
                "mistake_tag": tag,
                "challenges": sorted(list(cids)),
                "challenges_involved": sorted(list(cids)),
                "count": mistake_counts[tag],
                "occurrence_count": mistake_counts[tag]
            })

    return sorted(recurring, key=lambda x: x["count"], reverse=True)


def calculate_mastery(history: List[Dict[str, Any]], challenges_by_id: Dict[str, Dict[str, Any]]) -> Dict[str, float]:
    """
    Computes mastery for each core concept (0 to 100):
    Baseline: 50.0
    Pass with 0 hints: +10
    Pass with hints: +5
    Fail: -3
    """
    mastery = {c: 50.0 for c in CORE_CONCEPTS}

    for sub in history:
        cid = sub["challenge_id"]
        cdata = challenges_by_id.get(cid, {})
        concepts = cdata.get("concepts", [])
        if not concepts and "concept" in cdata:
            concepts = [cdata["concept"]]

        if not concepts:
            continue

        hints_used = get_hints_used_count(sub["id"])

        if sub["passed"]:
            delta = 10.0 if hints_used == 0 else 5.0
        else:
            delta = -3.0

        for concept in concepts:
            # Match case-insensitively
            for core in CORE_CONCEPTS:
                if core.lower() == concept.lower():
                    mastery[core] = max(0.0, min(100.0, mastery[core] + delta))

    return mastery


def recommend_next_challenge(
    history: List[Dict[str, Any]],
    mastery: Dict[str, float],
    recurring_mistakes: List[Dict[str, Any]],
    all_challenges: List[Dict[str, Any]]
) -> Tuple[Dict[str, Any], str]:
    """
    Recommends the best next challenge to address recurring mistakes and lowest concepts.
    """
    solved_challenge_ids = {sub["challenge_id"] for sub in history if sub["passed"]}
    recurring_tags = {r["tag"] for r in recurring_mistakes}

    # Find the weakest concepts
    sorted_concepts = sorted(mastery.items(), key=lambda x: x[1])
    lowest_concept = sorted_concepts[0][0] if sorted_concepts else "Loops"

    best_challenge = None
    best_score = -9999
    best_reason = ""

    # Tag to concept mapping
    tag_concept_map = {
        "off_by_one": ["Indexing", "Loops", "Lists"],
        "unhandled_short_input": ["Input handling", "Lists", "Conditions"],
        "boundary_comparison": ["Conditions", "Functions"],
        "mutates_input": ["Lists", "Indexing"],
        "print_not_return": ["Functions"]
    }

    for c in all_challenges:
        cid = c.get("id", "")
        c_concepts = [x.lower() for x in c.get("concepts", [])]

        score = 0
        reasons = []

        # Penalize already solved challenges
        if cid in solved_challenge_ids:
            score -= 100

        # +45 Boost if challenge addresses a recurring mistake
        for tag in recurring_tags:
            related_concepts = [rc.lower() for rc in tag_concept_map.get(tag, [])]
            if any(rc in c_concepts for rc in related_concepts):
                score += 45
                reasons.append(f"address your recurring '{tag}' mistake across multiple challenges")
                break

        # Boost if challenge covers lowest mastery concept
        if lowest_concept.lower() in c_concepts:
            score += 30
            reasons.append(f"strengthen your lowest mastery concept ({lowest_concept} at {int(mastery[lowest_concept])}%)")

        if score > best_score:
            best_score = score
            best_challenge = c
            if reasons:
                best_reason = f"Recommended to {reasons[0]}."
            else:
                best_reason = "Reinforce foundational problem-solving and clean edge-case handling."

    if not best_challenge and all_challenges:
        best_challenge = all_challenges[0]
        best_reason = "Practice core algorithmic logic and test boundary handling."

    return best_challenge or {}, best_reason


def get_learner_profile(learner_id: str) -> Dict[str, Any]:
    """
    Returns full learner profile:
    - recurring mistakes (appear across >= 2 different challenges)
    - mastery per concept (0 to 100 or normalized 0..1)
    - next challenge with human-readable reason
    """
    all_challenges = load_all_challenges()
    challenges_by_id = {c.get("id"): c for c in all_challenges}

    history = get_learner_history(learner_id)
    recurring = calculate_recurring_mistakes(history)
    mastery = calculate_mastery(history, challenges_by_id)
    next_c, reason = recommend_next_challenge(history, mastery, recurring, all_challenges)

    # Calculate challenges attempted / solved / failed
    distinct_attempted_set = {s["challenge_id"] for s in history}
    distinct_solved_set = {s["challenge_id"] for s in history if s["passed"]}
    distinct_attempted = len(distinct_attempted_set)
    distinct_solved = len(distinct_solved_set)
    distinct_failed = len(distinct_attempted_set - distinct_solved_set)
    total_submissions = len(history)
    passed_count = sum(1 for s in history if s["passed"])
    failed_count = total_submissions - passed_count

    # Fetch user details if registered
    user_name = learner_id.split("@")[0] if "@" in learner_id else learner_id
    user_email = learner_id if "@" in learner_id else None

    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, name, email FROM users WHERE email = ? OR id = ?", (learner_id, learner_id))
        user_row = cursor.fetchone()
        if user_row:
            user_name = user_row["name"]
            user_email = user_row["email"]

    # Build formatted submission history
    submission_history = []
    for s in reversed(history[-20:]):
        cid = s["challenge_id"]
        cdata = challenges_by_id.get(cid, {})
        submission_history.append({
            "id": s["id"],
            "challenge_id": cid,
            "title": cdata.get("title", cid.replace("-", " ").title()),
            "difficulty": cdata.get("difficulty", "Easy"),
            "passed": s["passed"],
            "outcome": "Passed" if s["passed"] else "Failed",
            "mistake_tags": s.get("mistake_tags", []),
            "created_at": s.get("created_at")
        })

    return {
        "learner_id": learner_id,
        "user_name": user_name,
        "user_email": user_email,
        "recurring_mistakes": recurring,
        "mastery_per_concept": mastery,
        "mastery": {k.lower(): round(v / 100.0, 2) for k, v in mastery.items()},
        "overall_mastery": round(sum(mastery.values()) / max(1, len(mastery))),
        "challenges_attempted": distinct_attempted,
        "challenges_solved": distinct_solved,
        "challenges_failed": distinct_failed,
        "total_submissions": total_submissions,
        "passed_count": passed_count,
        "failed_count": failed_count,
        "history": submission_history,
        "next_challenge": {
            "id": next_c.get("id", "last-k-total"),
            "challenge_id": next_c.get("id", "last-k-total"),
            "title": next_c.get("title", "Total of the Last K Marks"),
            "difficulty": next_c.get("difficulty", "Easy"),
            "concepts": next_c.get("concepts", ["Lists", "Loops"]),
            "reason": reason
        },
        "recommended_next_challenge": {
            "challenge_id": next_c.get("id", "last-k-total"),
            "title": next_c.get("title", "Total of the Last K Marks"),
            "difficulty": next_c.get("difficulty", "Easy"),
            "concepts": next_c.get("concepts", ["Lists", "Loops"])
        },
        "recommendation_reason": reason,
        "reason": reason
    }
