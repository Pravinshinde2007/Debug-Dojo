import uuid
import json
import os
import re
from pathlib import Path
from typing import List, Dict, Any, Optional
from contextlib import asynccontextmanager
from fastapi import FastAPI, APIRouter, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from .db import init_db, get_db_connection, log_llm_call
from .runner import run_submission, run_custom_code
from .tagger import detect_mistakes
from .explain import explain_failure, get_progressive_hints, explain_custom_code_error
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
    error_msg: Optional[str] = None
    error_type: Optional[str] = None
    error_line: Optional[int] = None


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
    overall_outcome: Optional[str] = "passed"
    error_type: Optional[str] = None
    error_line: Optional[int] = None
    error_msg: Optional[str] = None
    total_hints: Optional[int] = 4
    failed_test_num: Optional[int] = None
    failed_test_call: Optional[str] = None
    failed_test_expected: Optional[str] = None
    failed_test_got: Optional[str] = None
    visible_test_results: Optional[List[VisibleTestResult]] = None
    hidden_test_outcomes: Optional[List[HiddenTestResult]] = None


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


class CustomDebugRequest(BaseModel):
    code: Optional[str] = ""
    document_text: Optional[str] = None
    learner_id: Optional[str] = "demo-learner"


class CustomDebugResponse(BaseModel):
    success: bool
    outcome: str  # passed | syntax_error | runtime_error | timeout
    error_type: Optional[str] = None
    error_line: Optional[int] = None
    error_msg: Optional[str] = None
    explanation: str
    hints: List[str]
    mistake_tags: List[str]
    stdout: str
    extracted_from_doc: bool = False
    cleaned_code: str


# --- Challenge Loader Helper ---

def find_challenge(challenge_id: str) -> Optional[Dict[str, Any]]:
    challenges_dir = BASE_DIR / "challenges"
    cid = challenge_id.strip()
    candidates = [
        challenges_dir / f"{cid}.json",
        challenges_dir / f"{cid.replace('_', '-')}.json",
        challenges_dir / f"{cid.replace('-', '_')}.json"
    ]
    if "vowel" in cid:
        candidates.extend([
            challenges_dir / "count-vowels.json",
            challenges_dir / "vowel-count.json"
        ])
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
            outcome=v["outcome"],
            error_msg=v.get("error_msg"),
            error_type=v.get("error_type"),
            error_line=v.get("error_line")
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
    overall_outcome = run_result.get("overall_outcome", "passed" if all_passed else "wrong output")
    first_error = run_result.get("first_error") or {}
    first_failed = run_result.get("first_failed_test") or {}

    diff = str(challenge.get("difficulty") or "Easy").lower()
    total_hints = 5 if diff == "easy" else 4 if diff == "medium" else 3

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
        passed=all_passed,
        overall_outcome=overall_outcome,
        error_type=first_error.get("error_type"),
        error_line=first_error.get("error_line"),
        error_msg=first_error.get("error_msg"),
        total_hints=total_hints,
        failed_test_num=first_failed.get("test"),
        failed_test_call=first_failed.get("call"),
        failed_test_expected=str(first_failed.get("expected", "")) if first_failed.get("expected") is not None else None,
        failed_test_got=str(first_failed.get("got", "")) if first_failed.get("got") is not None else None,
        visible_test_results=visible_tests,
        hidden_test_outcomes=hidden_tests
    )


@router.post("/hint", response_model=HintResponse)
def request_hint(req: HintRequest):
    hint_index = 1
    challenge = None
    mistake_tags = []
    sub_code = ""
    visible_res = []

    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT COUNT(*) as count FROM hints_given WHERE submission_id = ?",
            (req.submission_id,)
        )
        row = cursor.fetchone()
        if row and row["count"] is not None:
            hint_index = row["count"] + 1

        cursor.execute(
            "SELECT challenge_id, code, visible_results, mistake_tags FROM submissions WHERE id = ?",
            (req.submission_id,)
        )
        sub_row = cursor.fetchone()
        if sub_row:
            sub_code = sub_row["code"] or ""
            challenge = find_challenge(sub_row["challenge_id"])
            try:
                mistake_tags = json.loads(sub_row["mistake_tags"])
            except Exception:
                pass
            try:
                visible_res = json.loads(sub_row["visible_results"])
            except Exception:
                pass

    diff = str(challenge.get("difficulty") or "Easy").lower() if challenge else "easy"
    total_hints = 5 if diff == "easy" else 4 if diff == "medium" else 3
    hint_level = min(hint_index, total_hints)

    test_run_data = {}
    if visible_res:
        for vr in visible_res:
            if vr.get("outcome") != "passed":
                test_run_data["first_failed_test"] = vr
                if vr.get("error_line"):
                    test_run_data["first_error"] = {
                        "error_type": vr.get("error_type") or "RuntimeError",
                        "error_line": vr.get("error_line"),
                        "error_msg": vr.get("error_msg") or vr.get("outcome")
                    }
                elif vr.get("outcome") == "runtime_error":
                    test_run_data["first_error"] = {
                        "error_type": vr.get("error_type") or "RuntimeError",
                        "error_line": None,
                        "error_msg": vr.get("error_msg") or vr.get("outcome")
                    }
                break

    if challenge:
        hints_ladder = get_progressive_hints(challenge, mistake_tags, test_run_data, code=sub_code)
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

    if total_hints == 5:
        HINT_TYPES = {
            1: "General concept",
            2: "Line of error & where to look",
            3: "Input boundary trap",
            4: "Underlying cause",
            5: "Debugging strategy"
        }
    elif total_hints == 4:
        HINT_TYPES = {
            1: "Core invariant & concept",
            2: "Line & variable inspection",
            3: "Underlying mechanism",
            4: "Debugging strategy"
        }
    else:
        HINT_TYPES = {
            1: "Algorithmic invariant",
            2: "Line of state transition",
            3: "Correction strategy"
        }

    return HintResponse(
        submission_id=req.submission_id,
        hint=hint_text,
        level=hint_level,
        total_levels=total_hints,
        hint_index=hint_level,
        total_hints=total_hints,
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


def extract_python_from_doc(doc_text: str) -> str:
    """
    Extracts Python code from document/text (e.g. markdown code blocks, snippets).
    """
    if not doc_text:
        return ""

    # Check for markdown code fences ```python ... ``` or ``` ... ```
    pattern = re.compile(r"```(?:python|py)?\s*\n(.*?)```", re.DOTALL | re.IGNORECASE)
    matches = pattern.findall(doc_text)
    if matches:
        return "\n\n".join(m.strip() for m in matches if m.strip())

    return doc_text.strip()


@router.post("/analyze-custom", response_model=CustomDebugResponse)
def analyze_custom_code(req: CustomDebugRequest):
    """
    Analyzes and executes learner-pasted Python code or extracted document code in an isolated
    subprocess sandbox. Explains errors in plain language with progressive non-revealing hints.
    """
    raw_code = req.code or ""
    extracted_from_doc = False

    if not raw_code.strip() and req.document_text:
        raw_code = extract_python_from_doc(req.document_text)
        extracted_from_doc = True

    if not raw_code.strip():
        return CustomDebugResponse(
            success=False,
            outcome="syntax_error",
            error_type="EmptyCodeError",
            error_line=1,
            error_msg="No Python code was provided to test.",
            explanation="Please paste your Python code or document snippet into the editor first.",
            hints=[
                "Write or paste Python code into the editor.",
                "Ensure your code has at least one executable statement or function.",
                "You can also paste a markdown document containing code blocks.",
                "Click 'Analyze & Run' to execute it safely in the sandbox."
            ],
            mistake_tags=["unhandled_short_input"],
            stdout="",
            extracted_from_doc=extracted_from_doc,
            cleaned_code=raw_code
        )

    # 1. Execute safely in isolated subprocess sandbox (Rule 1)
    run_res = run_custom_code(raw_code)

    outcome = run_res.get("outcome", "runtime_error")
    error_type = run_res.get("error_type")
    error_line = run_res.get("error_line")
    error_msg = run_res.get("error_msg")
    stdout = run_res.get("stdout", "")

    # 2. Mistake tagger AST inspection
    dummy_test_data = {
        "_detailed_data": [{
            "outcome": outcome,
            "stdout": stdout,
            "got": run_res.get("return_val"),
            "expected": None,
            "error_msg": error_msg
        }]
    }
    mistake_tags = detect_mistakes(raw_code, dummy_test_data, {"id": "custom-code"})

    # 3. Plain language explanation and 4 progressive hints with leak guard
    explanation_res = explain_custom_code_error(
        error_type=error_type,
        error_line=error_line,
        error_msg=error_msg,
        code=raw_code,
        mistake_tags=mistake_tags
    )

    success = outcome == "passed" and not error_type

    # 4. Log LLM / analysis event
    log_llm_call(
        prompt=f"Analyze custom code error: {error_type} {error_msg}",
        response=explanation_res["explanation"],
        context=f"custom_debug:{error_type or 'success'}"
    )

    return CustomDebugResponse(
        success=success,
        outcome=outcome,
        error_type=error_type,
        error_line=error_line,
        error_msg=error_msg,
        explanation=explanation_res["explanation"],
        hints=explanation_res["hints"],
        mistake_tags=mistake_tags,
        stdout=stdout,
        extracted_from_doc=extracted_from_doc,
        cleaned_code=raw_code
    )


# Mount router at both root ("") and "/api" so rewrites with or without prefix work seamlessly
app.include_router(router, prefix="")
app.include_router(router, prefix="/api")
