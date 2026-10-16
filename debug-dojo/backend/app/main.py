import uuid
import json
from typing import List, Dict, Any, Optional
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from .db import init_db, get_db_connection
from .learner import get_learner_profile
from .llm import generate_hint

from contextlib import asynccontextmanager

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

# CORS configuration for Vite dev server
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
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


class HintRequest(BaseModel):
    submission_id: str


class HintResponse(BaseModel):
    submission_id: str
    hint: str
    level: int
    total_levels: int
    hint_index: Optional[int] = None
    total_hints: Optional[int] = None



class LearnerProfileResponse(BaseModel):
    learner_id: str
    recurring_mistakes: List[str]
    mastery_per_concept: Dict[str, float]
    next_challenge: Dict[str, Any]
    reason: str


# --- Router for Endpoints ---
from fastapi import APIRouter

router = APIRouter()


@router.get("/health")
def health_check():
    return {"status": "ok", "service": "Debug Dojo"}


@router.post("/submit", response_model=SubmitResponse)
def submit_code(req: SubmitRequest):
    submission_id = f"sub_{uuid.uuid4().hex[:12]}"
    
    # Stage 1 response adhering exactly to final shape
    visible_tests = [
        VisibleTestResult(
            test=1,
            call="solution()",
            expected="10",
            got="10",
            outcome="passed"
        )
    ]
    hidden_tests = [
        HiddenTestResult(
            test=2,
            outcome="passed"
        )
    ]
    mistake_tags: List[str] = []
    explanation = "All tests passed! Great job."

    # Persist in SQLite
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
                1
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
        explanation=explanation
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

    hint_text = generate_hint({"id": req.submission_id}, hint_index)

    # Persist hint in hints_given
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO hints_given (submission_id, learner_id, hint_index, hint_text)
            VALUES (?, ?, ?, ?)
            """,
            (req.submission_id, "anonymous_learner", hint_index, hint_text)
        )
        conn.commit()

    return HintResponse(
        submission_id=req.submission_id,
        hint=hint_text,
        level=hint_index,
        total_levels=4,
        hint_index=hint_index,
        total_hints=4
    )


@router.get("/challenges")
def get_challenges():
    """Rule 2: Hidden tests stay hidden. Only public challenge metadata is returned, never tests."""
    challenges_dir = BASE_DIR / "challenges"
    challenges = []
    if challenges_dir.exists():
        for file in challenges_dir.glob("*.json"):
            try:
                with open(file, "r", encoding="utf-8") as f:
                    cdata = json.load(f)
                    challenges.append({
                        "id": cdata.get("id"),
                        "title": cdata.get("title"),
                        "difficulty": cdata.get("difficulty", "beginner"),
                        "concepts": [cdata.get("concept", "loops")] if isinstance(cdata.get("concept"), str) else cdata.get("concepts", []),
                        "description": cdata.get("description", ""),
                        "starter_code": cdata.get("starter_code", "")
                    })
            except Exception:
                pass
    if not challenges:
        challenges = [
            {
                "id": "sum_last_k",
                "title": "Total of the Last K Marks",
                "difficulty": "beginner",
                "concepts": ["loops", "lists", "slicing"],
                "description": "Rohan's score tracker needs to compute the sum of the last k marks in a list of scores.\nIf k is larger than the list, sum all available marks. If k <= 0, return 0.",
                "starter_code": "def sum_last_k(scores, k):\n    # Write your solution here\n    if k <= 0:\n        return 0\n    return sum(scores[-k:])\n"
            }
        ]
    return challenges


@router.get("/learner/{learner_id}", response_model=LearnerProfileResponse)
def get_learner(learner_id: str):
    profile = get_learner_profile(learner_id)
    return LearnerProfileResponse(
        learner_id=profile["learner_id"],
        recurring_mistakes=profile["recurring_mistakes"],
        mastery_per_concept=profile["mastery_per_concept"],
        next_challenge=profile["next_challenge"],
        reason=profile["reason"]
    )


# Mount router at both root ("") and "/api" so rewrites with or without prefix work seamlessly
app.include_router(router, prefix="")
app.include_router(router, prefix="/api")


