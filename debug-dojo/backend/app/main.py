import uuid
import json
import os
from pathlib import Path
from typing import List, Dict, Any, Optional
from contextlib import asynccontextmanager
from fastapi import FastAPI, APIRouter, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from .db import init_db, get_db_connection, log_llm_call
from .runner import run_submission
from .tagger import detect_mistakes
from .explain import explain_failure, get_progressive_hints
from .learner import get_learner_profile
from .llm import generate_hint, leak_guard

BASE_DIR = Path(__file__).resolve().parent.parent


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(
    title="Debug Dojo API",
    description="Debug Dojo: Safe coding coach for beginners with progressive hints and learner mastery tracking",
    version="1.0.0",
    lifespan=lifespan
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:5174",
        "http://localhost:3000",
        "*"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# --- Request & Response Models ---

class SubmitRequest(BaseModel):
    learner_id: str
    challenge_id: str
    code: str


class VisibleTestResult(BaseModel):
    test: int
    call: str
    expected: str
    got: str
    outcome: str  # passed | wrong_output | runtime_error | timeout


class HiddenTestResult(BaseModel):
    test: int
    outcome: str  # passed | wrong_output | runtime_error | timeout


class SubmitResponse(BaseModel):
    submission_id: str
    learner_id: str
    challenge_id: str
    visible: List[VisibleTestResult]
    hidden: List[HiddenTestResult]
    mistake_tags: List[str]
    explanation: str
    passed: Optional[bool] = None


class HintRequest(BaseModel):
    submission_id: str


class HintResponse(BaseModel):
    submission_id: str
    hint: str
    level: int
    total_levels: int
    hint_index: Optional[int] = None
    total_hints: Optional[int] = None
    hint_level: Optional[int] = None
    hint_type: Optional[str] = None


class LearnerProfileResponse(BaseModel):
    learner_id: str
    recurring_mistakes: List[Dict[str, Any]]
    mastery_per_concept: Dict[str, float]
    mastery: Optional[Dict[str, float]] = None
    overall_mastery: Optional[int] = None
    challenges_attempted: Optional[int] = None
    challenges_solved: Optional[int] = None
    next_challenge: Dict[str, Any]
    recommended_next_challenge: Optional[Dict[str, Any]] = None
    recommendation_reason: Optional[str] = None
    reason: str


# --- Challenge Loader Helper ---

def find_challenge(challenge_id: str) -> Optional[Dict[str, Any]]:
    challenges_dir = BASE_DIR / "challenges"
    candidates = [
        challenges_dir / f"{challenge_id}.json",
        challenges_dir / f"{challenge_id.replace('_', '-')}.json",
        challenges_dir / f"{challenge_id.replace('-', '_')}.json"
    ]
    for p in candidates:
        if p.exists():
            try:
                with open(p, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
    return None


# --- Router for Endpoints ---

router = APIRouter()


@router.get("/health")
def health_check():
    return {"status": "ok", "service": "Debug Dojo"}


@router.get("/challenges")
def get_challenges():
    """Rule 2: Hidden tests stay hidden. Only public challenge metadata is returned, never tests."""
    challenges_dir = BASE_DIR / "challenges"
    challenges = []
    if challenges_dir.exists():
        for file in sorted(challenges_dir.glob("*.json")):
            try:
                with open(file, "r", encoding="utf-8") as f:
                    cdata = json.load(f)
                    concepts = cdata.get("concepts", [])
                    if not concepts and "concept" in cdata:
                        concepts = [cdata["concept"]]
                    challenges.append({
                        "id": cdata.get("id"),
                        "title": cdata.get("title"),
                        "difficulty": cdata.get("difficulty", "Easy"),
                        "concepts": concepts,
                        "description": cdata.get("description", ""),
                        "starter_code": cdata.get("starter_code", "")
                    })
            except Exception:
                pass
    return challenges


@router.post("/submit", response_model=SubmitResponse)
def submit_code(req: SubmitRequest):
    submission_id = f"sub_{uuid.uuid4().hex[:12]}"
    challenge = find_challenge(req.challenge_id)
    if not challenge:
        # Fallback challenge template if challenge ID not recognized
        challenge = {
            "id": req.challenge_id,
            "title": req.challenge_id.replace("-", " ").title(),
            "visible_tests": [{"test": 1, "call": "solution()", "args": [], "expected": 10}],
            "hidden_tests": [{"test": 2, "kind": "boundary case", "args": [], "expected": 10}],
        }

    # 1. Run submission in separate, isolated child process (Rule 1)
    run_result = run_submission(req.code, challenge)

    # 2. Detect mistakes deterministically (Rule 5)
    mistake_tags = detect_mistakes(req.code, run_result, challenge)

    # 3. Plain language explanation (Rule 2)
    explanation = explain_failure(run_result, mistake_tags, challenge)

    visible_tests = [
        VisibleTestResult(
            test=v["test"],
            call=v["call"],
            expected=str(v["expected"]),
            got=str(v["got"]),
            outcome=v["outcome"]
        )
        for v in run_result["visible"]
    ]

    # Rule 2: Hidden tests are secret
    hidden_tests = [
        HiddenTestResult(
            test=h["test"],
            outcome=h["outcome"]
        )
        for h in run_result["hidden"]
    ]

    all_passed = run_result.get("all_passed", False)

    # 4. Persist in SQLite
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO submissions (
                id, learner_id, challenge_id, code,
                visible_results, hidden_results, mistake_tags,
                explanation, passed
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                submission_id,
                req.learner_id,
                req.challenge_id,
                req.code,
                json.dumps([v.model_dump() for v in visible_tests]),
                json.dumps([h.model_dump() for h in hidden_tests]),
                json.dumps(mistake_tags),
                explanation,
                1 if all_passed else 0
            )
        )
        conn.commit()

    return SubmitResponse(
        submission_id=submission_id,
        learner_id=req.learner_id,
        challenge_id=req.challenge_id,
        visible=visible_tests,
        hidden=hidden_tests,
        mistake_tags=mistake_tags,
        explanation=explanation,
        passed=all_passed
    )


@router.post("/hint", response_model=HintResponse)
def request_hint(req: HintRequest):
    # Fetch existing hints count for this submission
    hint_index = 1
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT COUNT(*) as count FROM hints_given WHERE submission_id = ?",
            (req.submission_id,)
        )
        row = cursor.fetchone()
        if row and row["count"] is not None:
            hint_index = row["count"] + 1

    # Clamp hint_index to maximum 4
    hint_level = min(hint_index, 4)

    # Query submission to inspect challenge and mistake tags
    challenge = None
    mistake_tags = []
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT challenge_id, mistake_tags FROM submissions WHERE id = ?",
            (req.submission_id,)
        )
        sub_row = cursor.fetchone()
        if sub_row:
            challenge = find_challenge(sub_row["challenge_id"])
            try:
                mistake_tags = json.loads(sub_row["mistake_tags"])
            except Exception:
                pass

    if challenge:
        hints_ladder = get_progressive_hints(challenge, mistake_tags, {})
        hint_text = hints_ladder[min(hint_level - 1, len(hints_ladder) - 1)]
    else:
        hint_text = generate_hint({"id": req.submission_id}, hint_level)

    hint_text = leak_guard(hint_text)

    # Persist hint in hints_given
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO hints_given (submission_id, learner_id, hint_index, hint_text)
            VALUES (?, ?, ?, ?)
            """,
            (req.submission_id, "anonymous_learner", hint_level, hint_text)
        )
        conn.commit()

    HINT_TYPES = {
        1: "General concept",
        2: "Where to investigate",
        3: "Underlying cause",
        4: "Debugging strategy"
    }

    return HintResponse(
        submission_id=req.submission_id,
        hint=hint_text,
        level=hint_level,
        total_levels=4,
        hint_index=hint_level,
        total_hints=4,
        hint_level=hint_level,
        hint_type=HINT_TYPES.get(hint_level, "Guidance")
    )


@router.get("/learner/{learner_id}", response_model=LearnerProfileResponse)
def get_learner(learner_id: str):
    profile = get_learner_profile(learner_id)
    return LearnerProfileResponse(
        learner_id=profile["learner_id"],
        recurring_mistakes=profile["recurring_mistakes"],
        mastery_per_concept=profile["mastery_per_concept"],
        mastery=profile.get("mastery"),
        overall_mastery=profile.get("overall_mastery"),
        challenges_attempted=profile.get("challenges_attempted"),
        challenges_solved=profile.get("challenges_solved"),
        next_challenge=profile["next_challenge"],
        recommended_next_challenge=profile.get("recommended_next_challenge"),
        recommendation_reason=profile.get("recommendation_reason"),
        reason=profile["reason"]
    )


# Mount router at both root ("") and "/api" so rewrites with or without prefix work seamlessly
app.include_router(router, prefix="")
app.include_router(router, prefix="/api")
