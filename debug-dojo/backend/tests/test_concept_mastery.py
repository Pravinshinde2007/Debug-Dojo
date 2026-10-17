import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

import pytest
from app.learner import (
    calculate_hint_weighted_delta,
    get_concept_status_label,
    recommend_next_challenge,
    get_learner_profile,
    PRIMARY_SKILLS,
)
from app.db import get_db_connection


def test_hint_weighted_scoring_deltas():
    """
    Verifies that:
    - Passing without hints earns the most credit (+15%).
    - Passing after hints earns graduated less credit.
    - Failed attempts do not increase mastery (-4%).
    """
    assert calculate_hint_weighted_delta(passed=True, hints_used=0) == 15.0
    assert calculate_hint_weighted_delta(passed=True, hints_used=1) == 10.0
    assert calculate_hint_weighted_delta(passed=True, hints_used=2) == 7.0
    assert calculate_hint_weighted_delta(passed=True, hints_used=3) == 4.0
    assert calculate_hint_weighted_delta(passed=True, hints_used=4) == 2.0
    assert calculate_hint_weighted_delta(passed=True, hints_used=10) == 2.0

    # Failed attempts
    assert calculate_hint_weighted_delta(passed=False, hints_used=0) == -4.0
    assert calculate_hint_weighted_delta(passed=False, hints_used=3) == -4.0


def test_concept_status_labels():
    """
    Verifies status label assignment matching the prompt specifications:
    - 'Several successful attempts' (high mastery, positive momentum)
    - 'Some repeated mistakes' (mid-range mastery)
    - 'Needs more practice' (low mastery or consecutive failures)
    """
    # High score
    assert get_concept_status_label(85.0, consecutive_fails=0, consecutive_passes=3, total_attempts=5) == "Several successful attempts"
    assert get_concept_status_label(75.0, consecutive_fails=0, consecutive_passes=2, total_attempts=3) == "Several successful attempts"

    # Mid score
    assert get_concept_status_label(50.0, consecutive_fails=0, consecutive_passes=1, total_attempts=4) == "Some repeated mistakes"
    assert get_concept_status_label(65.0, consecutive_fails=0, consecutive_passes=1, total_attempts=3) == "Some repeated mistakes"

    # Low score
    assert get_concept_status_label(25.0, consecutive_fails=0, consecutive_passes=0, total_attempts=3) == "Needs more practice"
    assert get_concept_status_label(35.0, consecutive_fails=0, consecutive_passes=0, total_attempts=2) == "Needs more practice"

    # Consecutive failures downgrade status even if score is moderate
    assert get_concept_status_label(60.0, consecutive_fails=2, consecutive_passes=0, total_attempts=4) == "Needs more practice"


def test_illustrative_profile_for_new_learner():
    """
    When a learner has no submissions yet, the profile returns the exact illustrative
    benchmark values described in prompt 9:
    - Loops: 85% ("Several successful attempts")
    - Lists and indexing: 50% ("Some repeated mistakes")
    - Edge cases: 25% ("Needs more practice")
    - Plus disclaimer note.
    """
    unique_new_learner = "test_illustrative_newbie_9999"
    profile = get_learner_profile(unique_new_learner)

    assert "skills_by_concept" in profile
    assert "disclaimer" in profile
    assert "estimates, not proof of a student's ability" in profile["disclaimer"]

    skills_dict = {s["concept"]: s for s in profile["skills_by_concept"]}

    assert "Loops" in skills_dict
    assert skills_dict["Loops"]["mastery"] == 85
    assert skills_dict["Loops"]["status"] == "Several successful attempts"
    assert skills_dict["Loops"]["is_illustrative"] is True

    assert "Lists and indexing" in skills_dict
    assert skills_dict["Lists and indexing"]["mastery"] == 50
    assert skills_dict["Lists and indexing"]["status"] == "Some repeated mistakes"

    assert "Edge cases" in skills_dict
    assert skills_dict["Edge cases"]["mastery"] == 25
    assert skills_dict["Edge cases"]["status"] == "Needs more practice"


def test_repeated_failures_trigger_easier_practice():
    """
    Repeated failures in a concept should trigger a recommendation for easier practice
    in that concept to build foundational confidence.
    """
    learner_id = "test_struggling_learner_adaptive"

    with get_db_connection() as conn:
        cursor = conn.cursor()
        # Clean previous test entries
        cursor.execute("DELETE FROM submissions WHERE learner_id = ?", (learner_id,))
        cursor.execute("DELETE FROM hints_given WHERE submission_id LIKE 'sub_struggle_%'")

        # Insert 2 consecutive failures on an Edge cases / indexing challenge
        cursor.execute(
            """
            INSERT INTO submissions (id, learner_id, challenge_id, passed, visible_results, hidden_results, mistake_tags, explanation, code, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now', '-2 minutes'))
            """,
            ("sub_struggle_1", learner_id, "last-k-total", 0, "[]", "[]", '["unhandled_short_input", "off_by_one"]', "Explanation 1", "code1")
        )
        cursor.execute(
            """
            INSERT INTO submissions (id, learner_id, challenge_id, passed, visible_results, hidden_results, mistake_tags, explanation, code, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now', '-1 minute'))
            """,
            ("sub_struggle_2", learner_id, "last-k-total", 0, "[]", "[]", '["unhandled_short_input", "off_by_one"]', "Explanation 2", "code2")
        )
        conn.commit()

    profile = get_learner_profile(learner_id)
    rec = profile.get("next_challenge", {})
    reason = rec.get("reason", "").lower()

    # The reason should indicate easier practice or building confidence
    assert "easier practice" in reason or "confidence" in reason or "repeated" in reason or "boundary" in reason

    # Clean up
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM submissions WHERE learner_id = ?", (learner_id,))
        cursor.execute("DELETE FROM hints_given WHERE submission_id LIKE 'sub_struggle_%'")
        conn.commit()
