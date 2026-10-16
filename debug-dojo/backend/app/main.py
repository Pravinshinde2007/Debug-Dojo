import uuid
import json
from typing import List, Dict, Any, Optional
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from .db import init_db, get_db_connection
from .runner import run_submission
from .tagger import detect_mistakes
from .explain import explain_failure
from .learner import get_learner_profile
from .llm import generate_hint

app = FastAPI(
    title="Debug Dojo API",
    description="Debug Dojo: Safe coding coach for beginners with progressive hints and learner mastery tracking",
    version="1.0.0"
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


@app.on_event("startup")
def on_startup():
    init_db()


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
    hint_index: int
    total_hints: int


class LearnerProfileResponse(BaseModel):
    learner_id: str
    recurring_mistakes: List[str]
    mastery_per_concept: Dict[str, float]
    next_challenge: Dict[str, Any]
    reason: str


# --- Endpoints ---

@app.get("/api/health")
def health_check():
    return {"status": "ok", "service": "Debug Dojo"}


@app.post("/api/submit", response_model=SubmitResponse)
def submit_code(req: SubmitRequest):
    submission_id = f"sub_{uuid.uuid4().hex[:12]}"
    
    # Dummy / Stage 1 response adhering exactly to final shape
    visible_tests = [
        VisibleTestResult(
            test=1,
            call=f"solution()",
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
                json.dumps([v.dict() for v in visible_tests]),
                json.dumps([h.dict() for h in hidden_tests]),
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


@app.post("/api/hint", response_model=HintResponse)
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
        if row:
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
        hint_index=hint_index,
        total_hints=3
    )


@app.get("/api/learner/{learner_id}", response_model=LearnerProfileResponse)
def get_learner(learner_id: str):
    profile = get_learner_profile(learner_id)
    return LearnerProfileResponse(
        learner_id=profile["learner_id"],
        recurring_mistakes=profile["recurring_mistakes"],
        mastery_per_concept=profile["mastery_per_concept"],
        next_challenge=profile["next_challenge"],
        reason=profile["reason"]
    )
