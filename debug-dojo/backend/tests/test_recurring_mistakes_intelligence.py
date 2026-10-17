import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

import pytest
from app.learner import (
    COMPULSORY_MISTAKES,
    get_learner_mistakes_breakdown,
    calculate_recurring_mistakes,
    recommend_next_challenge,
    get_learner_profile,
    load_all_challenges
)
from app.db import get_db_connection


def test_five_compulsory_mistake_categories_present():
    """
    Verifies that the five compulsory mistake categories from Rule 8 are all present and distinct:
    1. off_by_one
    2. unhandled_short_input
    3. print_not_return
    4. boundary_comparison
    5. mutates_input
    """
    expected_categories = [
        "off_by_one",
        "unhandled_short_input",
        "print_not_return",
        "boundary_comparison",
        "mutates_input"
    ]
    for cat in expected_categories:
        assert cat in COMPULSORY_MISTAKES
        meta = COMPULSORY_MISTAKES[cat]
        assert "meaning" in meta and len(meta["meaning"]) > 0
        assert "example" in meta and len(meta["example"]) > 0
        assert "practice_focus" in meta and len(meta["practice_focus"]) > 0

    assert COMPULSORY_MISTAKES["off_by_one"]["meaning"] == "A loop or index is one position off"
    assert COMPULSORY_MISTAKES["unhandled_short_input"]["meaning"] == "Empty or short inputs are not handled"
    assert COMPULSORY_MISTAKES["print_not_return"]["meaning"] == "Printing the answer instead of returning it"
    assert COMPULSORY_MISTAKES["boundary_comparison"]["meaning"] == "Using the wrong comparison at a boundary"
    assert COMPULSORY_MISTAKES["mutates_input"]["meaning"] == "Modifying the original input when it should remain unchanged"


def test_single_challenge_repeated_mistake_not_recurring():
    """
    Rule 8 requirement:
    'If the learner makes the same mistake twice in the same challenge, that alone does not satisfy the requirement.'
    """
    history = [
        {
            "id": "sub_1",
            "challenge_id": "challenge_alpha",
            "passed": False,
            "mistake_tags": ["off_by_one"]
        },
        {
            "id": "sub_2",
            "challenge_id": "challenge_alpha",
            "passed": False,
            "mistake_tags": ["off_by_one"]
        }
    ]

    breakdown = get_learner_mistakes_breakdown(history)
    recurring = breakdown["recurring_mistakes"]
    isolated = breakdown["isolated_mistakes"]

    # Must NOT be in recurring
    assert len(recurring) == 0
    assert not any(r["tag"] == "off_by_one" for r in recurring)

    # Must be in isolated (tracked, but single challenge)
    assert len(isolated) == 1
    assert isolated[0]["tag"] == "off_by_one"
    assert isolated[0]["distinct_challenges_count"] == 1
    assert isolated[0]["count"] == 2
    assert isolated[0]["is_recurring"] is False


def test_multi_challenge_mistake_becomes_recurring():
    """
    Rule 8 requirement:
    'A category is recurring only when it appears in at least two different challenges.
    - Challenge A: The learner makes an off_by_one mistake.
    - Challenge B: The learner makes another off_by_one mistake.
    - Debug Dojo marks off_by_one as recurring.'
    """
    history = [
        {
            "id": "sub_a",
            "challenge_id": "challenge_a",
            "passed": False,
            "mistake_tags": ["off_by_one"]
        },
        {
            "id": "sub_b",
            "challenge_id": "challenge_b",
            "passed": False,
            "mistake_tags": ["off_by_one"]
        }
    ]

    breakdown = get_learner_mistakes_breakdown(history)
    recurring = breakdown["recurring_mistakes"]

    # Must be marked as recurring
    assert len(recurring) == 1
    rec = recurring[0]
    assert rec["tag"] == "off_by_one"
    assert rec["is_recurring"] is True
    assert rec["distinct_challenges_count"] == 2
    assert sorted(rec["challenges"]) == ["challenge_a", "challenge_b"]
    assert rec["meaning"] == "A loop or index is one position off"
    assert rec["example"] == "Stopping a loop one element too early"


def test_recommendation_targets_loop_boundaries_for_recurring_off_by_one():
    """
    Rule 8 requirement:
    '- Debug Dojo marks off_by_one as recurring.
     - Challenge C is recommended because it practises loop boundaries.'
    """
    all_challenges = load_all_challenges()
    history = [
        {"id": "s1", "challenge_id": "challenge_a", "passed": False, "mistake_tags": ["off_by_one"]},
        {"id": "s2", "challenge_id": "challenge_b", "passed": False, "mistake_tags": ["off_by_one"]}
    ]
    recurring = calculate_recurring_mistakes(history)
    mastery = {"Loops": 50.0, "Lists": 50.0, "Indexing": 50.0}

    next_c, reason = recommend_next_challenge(history, mastery, recurring, all_challenges)

    # Must recommend a challenge and reason referencing loop boundaries or recurring off_by_one
    assert "loop boundaries" in reason.lower()
    assert "off_by_one" in reason.lower()


def test_learner_profile_contains_rule8_structures():
    """
    Verifies that get_learner_profile endpoint returns recurring_mistakes,
    isolated_mistakes, and compulsory_mistake_categories.
    """
    learner_id = "test_rule8_learner_verification"
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM submissions WHERE learner_id = ?", (learner_id,))
        # 1. First submission on challenge_1 with boundary_comparison
        cursor.execute(
            """
            INSERT INTO submissions (id, learner_id, challenge_id, passed, visible_results, hidden_results, mistake_tags, explanation, code)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            ("sub_r8_1", learner_id, "clamp-score", 0, "[]", "[]", '["boundary_comparison"]', "Error 1", "code1")
        )
        # 2. Second submission on count-passes with boundary_comparison (different challenge!)
        cursor.execute(
            """
            INSERT INTO submissions (id, learner_id, challenge_id, passed, visible_results, hidden_results, mistake_tags, explanation, code)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            ("sub_r8_2", learner_id, "count-passes", 0, "[]", "[]", '["boundary_comparison"]', "Error 2", "code2")
        )
        # 3. Third submission on count-passes with print_not_return (same challenge!)
        cursor.execute(
            """
            INSERT INTO submissions (id, learner_id, challenge_id, passed, visible_results, hidden_results, mistake_tags, explanation, code)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            ("sub_r8_3", learner_id, "count-passes", 0, "[]", "[]", '["print_not_return"]', "Error 3", "code3")
        )
        conn.commit()

    profile = get_learner_profile(learner_id)

    # boundary_comparison should be recurring (appeared in clamp-score and count-passes)
    recurring_tags = [r["tag"] for r in profile["recurring_mistakes"]]
    assert "boundary_comparison" in recurring_tags

    # print_not_return should NOT be recurring (only appeared in count-passes)
    assert "print_not_return" not in recurring_tags

    # Check isolated_mistakes contains print_not_return
    isolated_tags = [im["tag"] for im in profile.get("isolated_mistakes", [])]
    assert "print_not_return" in isolated_tags

    # Check compulsory_mistake_categories exists
    compulsory_tags = [c["tag"] for c in profile.get("compulsory_mistake_categories", [])]
    assert "off_by_one" in compulsory_tags
    assert "boundary_comparison" in compulsory_tags

    # Clean up
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM submissions WHERE learner_id = ?", (learner_id,))
        conn.commit()
