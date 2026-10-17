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

FALLBACK_CHALLENGES = [
    {"id": "last-k-total", "title": "Last K Total", "difficulty": "Easy", "concepts": ["Lists", "Loops", "Indexing"], "short": "Add up the last k marks"},
    {"id": "count-passes", "title": "Count Passes", "difficulty": "Easy", "concepts": ["Loops", "Conditions"], "short": "Count how many students passed"},
    {"id": "find-index-of", "title": "Find Index of Element", "difficulty": "Easy", "concepts": ["Lists", "Loops", "Conditions"], "short": "Find the index of an element"}
]

def get_challenges_dir() -> Path:
    candidates = [
        Path(__file__).resolve().parent.parent / "challenges",
        Path(__file__).resolve().parent.parent.parent / "backend" / "challenges",
        Path(__file__).resolve().parent.parent.parent / "debug-dojo" / "backend" / "challenges",
        Path.cwd() / "challenges",
        Path.cwd() / "backend" / "challenges",
        Path.cwd() / "debug-dojo" / "backend" / "challenges",
    ]
    for c in candidates:
        if c.exists() and any(c.glob("*.json")):
            return c
    return Path(__file__).resolve().parent.parent / "challenges"

CHALLENGES_DIR = get_challenges_dir()


def load_all_challenges() -> List[Dict[str, Any]]:
    challenges = []
    c_dir = get_challenges_dir()
    if c_dir.exists():
        for f in c_dir.glob("*.json"):
            try:
                with open(f, "r", encoding="utf-8") as fp:
                    data = json.load(fp)
                    challenges.append(data)
            except Exception:
                pass
    if not challenges:
        return list(FALLBACK_CHALLENGES)
    return challenges


def get_learner_history(learner_id: str) -> List[Dict[str, Any]]:
    try:
        # Find both id and email for this learner if registered
        identifiers = [learner_id]
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id, email FROM users WHERE id = ? OR email = ?", (learner_id, learner_id.strip().lower()))
            u = cursor.fetchone()
            if u:
                identifiers = list(set([u["id"], u["email"]]))

            placeholders = ",".join(["?"] * len(identifiers))
            cursor.execute(
                f"""
                SELECT id, learner_id, challenge_id, code, visible_results, passed, mistake_tags, explanation, created_at
                FROM submissions
                WHERE learner_id IN ({placeholders})
                ORDER BY created_at ASC
                """,
                identifiers
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
                "code": r["code"],
                "passed": bool(r["passed"]),
                "mistake_tags": tags,
                "created_at": r["created_at"]
            })
        return history
    except Exception:
        return []


def get_hints_used_count(submission_id: str) -> int:
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT COUNT(*) as count FROM hints_given WHERE submission_id = ?",
                (submission_id,)
            )
            row = cursor.fetchone()
            return row["count"] if row and row["count"] is not None else 0
    except Exception:
        return 0


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
    distinct_attempted_set = {s["challenge_id"] for s in history if s["challenge_id"] != "custom-code"}
    distinct_solved_set = {s["challenge_id"] for s in history if s["passed"] and s["challenge_id"] != "custom-code"}
    distinct_attempted = len(distinct_attempted_set)
    distinct_solved = len(distinct_solved_set)
    distinct_failed = len(distinct_attempted_set - distinct_solved_set)
    custom_debug_count = sum(1 for s in history if s["challenge_id"] == "custom-code")
    total_submissions = len(history)
    passed_count = sum(1 for s in history if s["passed"])
    failed_count = total_submissions - passed_count

    # Fetch user details if registered
    user_name = learner_id.split("@")[0] if "@" in learner_id else learner_id
    user_email = learner_id if "@" in learner_id else None
    identifiers = [learner_id]

    total_interactions = total_submissions
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id, name, email FROM users WHERE email = ? OR id = ?", (learner_id, learner_id.strip().lower()))
            user_row = cursor.fetchone()
            if user_row:
                user_name = user_row["name"]
                user_email = user_row["email"]
                identifiers = list(set([user_row["id"], user_row["email"]]))

            # Count total measured interaction events (submissions, hints, custom debug runs)
            placeholders = ",".join(["?"] * len(identifiers))
            cursor.execute(f"SELECT COUNT(*) as cnt FROM learner_events WHERE learner_id IN ({placeholders})", identifiers)
            row = cursor.fetchone()
            if row and row["cnt"] is not None:
                total_interactions = row["cnt"]
    except Exception:
        pass

    # Build formatted submission history from real SQLite rows
    submission_history = []
    for s in reversed(history[-25:]):
        cid = s["challenge_id"]
        if cid == "custom-code":
            title = "Custom Python Code Debug"
            diff = "Practice"
        else:
            cdata = challenges_by_id.get(cid, {})
            title = cdata.get("title", cid.replace("-", " ").title())
            diff = cdata.get("difficulty", "Easy")

        raw_code = s.get("code") or ""
        code_preview = raw_code[:120] + "..." if len(raw_code) > 120 else raw_code

        submission_history.append({
            "id": s["id"],
            "challenge_id": cid,
            "title": title,
            "difficulty": diff,
            "passed": s["passed"],
            "outcome": "Passed" if s["passed"] else "Failed",
            "mistake_tags": s.get("mistake_tags", []),
            "code_snippet": code_preview,
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
        "custom_debug_count": custom_debug_count,
        "total_interactions": max(total_interactions, total_submissions),
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
