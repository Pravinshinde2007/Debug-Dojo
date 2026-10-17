import uuid
import json
import os
import re
import ast
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from contextlib import asynccontextmanager
from fastapi import FastAPI, APIRouter, HTTPException, UploadFile, File, Header, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from .db import (
    init_db,
    get_db_connection,
    log_llm_call,
    create_user,
    authenticate_user,
    get_user_by_email,
    get_user_by_id,
    create_jwt_token,
    verify_jwt_token,
    revoke_jwt_token
)
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


@app.middleware("http")
async def resolve_vercel_rewrite_path(request: Request, call_next):
    # When Vercel rewrites incoming requests to /api/index, inspect Vercel headers for original path
    vercel_path = (
        request.headers.get("x-matched-path") or 
        request.headers.get("x-invoke-path") or
        request.headers.get("x-forwarded-uri")
    )
    if vercel_path and request.scope.get("path") in ("/api/index", "/api", "/index", "/"):
        clean_path = vercel_path.split("?")[0]
        if clean_path and clean_path not in ("/api/index", "/api", "/index", "/"):
            request.scope["path"] = clean_path
    response = await call_next(request)
    return response


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
    user_name: Optional[str] = None
    user_email: Optional[str] = None
    recurring_mistakes: List[Dict[str, Any]]
    isolated_mistakes: Optional[List[Dict[str, Any]]] = None
    compulsory_mistake_categories: Optional[List[Dict[str, Any]]] = None
    skills_by_concept: Optional[List[Dict[str, Any]]] = None
    mastery_per_concept: Dict[str, float]
    mastery: Optional[Dict[str, float]] = None
    overall_mastery: Optional[int] = None
    disclaimer: Optional[str] = "These values are estimates, not proof of a student's ability. Updated after every submission."
    challenges_attempted: Optional[int] = None
    challenges_solved: Optional[int] = None
    challenges_failed: Optional[int] = None
    custom_debug_count: Optional[int] = None
    total_interactions: Optional[int] = None
    total_submissions: Optional[int] = None
    passed_count: Optional[int] = None
    failed_count: Optional[int] = None
    history: Optional[List[Dict[str, Any]]] = None
    submission_history: Optional[List[Dict[str, Any]]] = None
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


class RegisterRequest(BaseModel):
    name: Optional[str] = ""
    email: str
    password: str


class LoginRequest(BaseModel):
    email: str
    password: str


class UserProfile(BaseModel):
    id: str
    name: str
    email: str
    created_at: Optional[str] = None


class AuthResponse(BaseModel):
    success: bool
    token: Optional[str] = None
    token_type: str = "Bearer"
    user: Optional[UserProfile] = None
    message: str = ""


class UploadDocResponse(BaseModel):
    success: bool
    is_python: bool
    filename: str
    code: Optional[str] = ""
    message: str



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
def submit_code(req: SubmitRequest, authorization: Optional[str] = Header(None)):
    submission_id = f"sub_{uuid.uuid4().hex[:12]}"
    effective_learner_id = req.learner_id
    if authorization and authorization.lower().startswith("bearer "):
        auth_user = verify_jwt_token(authorization[7:].strip())
        if auth_user:
            effective_learner_id = auth_user["id"]

    try:
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
            for v in run_result.get("visible", [])
        ]

        # Rule 2: Hidden tests are secret
        hidden_tests = [
            HiddenTestResult(
                test=h["test"],
                outcome=h["outcome"]
            )
            for h in run_result.get("hidden", [])
        ]

        all_passed = run_result.get("all_passed", False)
        overall_outcome = run_result.get("overall_outcome", "passed" if all_passed else "wrong output")
        first_error = run_result.get("first_error") or {}
        first_failed = run_result.get("first_failed_test") or {}

        diff = str(challenge.get("difficulty") or "Easy").lower()
        total_hints = 5 if diff == "easy" else 4 if diff == "medium" else 3

        # 4. Persist in SQLite
        try:
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
                        effective_learner_id,
                        req.challenge_id,
                        req.code,
                        json.dumps([v.model_dump() for v in visible_tests]),
                        json.dumps([h.model_dump() for h in hidden_tests]),
                        json.dumps(mistake_tags),
                        explanation,
                        1 if all_passed else 0
                    )
                )
                # Log interaction event for measuring user activities
                cursor.execute(
                    """
                    INSERT INTO learner_events (learner_id, event_type, payload)
                    VALUES (?, ?, ?)
                    """,
                    (
                        effective_learner_id,
                        "challenge_submission",
                        json.dumps({
                            "submission_id": submission_id,
                            "challenge_id": req.challenge_id,
                            "passed": all_passed,
                            "outcome": overall_outcome,
                            "mistake_tags": mistake_tags
                        })
                    )
                )
                conn.commit()
        except Exception as db_exc:
            print(f"Non-fatal DB save error in submit_code: {db_exc}")

        return SubmitResponse(
            submission_id=submission_id,
            learner_id=effective_learner_id,
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
    except Exception as exc:
        print(f"Unexpected error in submit_code: {exc}")
        return SubmitResponse(
            submission_id=submission_id,
            learner_id=effective_learner_id,
            challenge_id=req.challenge_id,
            visible=[],
            hidden=[],
            mistake_tags=[],
            explanation=f"Sandbox execution error: {str(exc)}",
            passed=False,
            overall_outcome="runtime error",
            error_type="SandboxError",
            error_line=None,
            error_msg=str(exc),
            total_hints=3,
            failed_test_num=1,
            failed_test_call=f"{req.challenge_id}()",
            failed_test_expected=None,
            failed_test_got=None,
            visible_test_results=[],
            hidden_test_outcomes=[]
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
            "SELECT learner_id, challenge_id, code, visible_results, mistake_tags FROM submissions WHERE id = ?",
            (req.submission_id,)
        )
        sub_row = cursor.fetchone()
        sub_learner_id = "anonymous_learner"
        if sub_row:
            sub_learner_id = sub_row["learner_id"] or "anonymous_learner"
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

    # Persist hint in hints_given and log learner event
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO hints_given (submission_id, learner_id, hint_index, hint_text)
            VALUES (?, ?, ?, ?)
            """,
            (req.submission_id, sub_learner_id, hint_level, hint_text)
        )
        cursor.execute(
            """
            INSERT INTO learner_events (learner_id, event_type, payload)
            VALUES (?, ?, ?)
            """,
            (
                sub_learner_id,
                "hint_requested",
                json.dumps({
                    "submission_id": req.submission_id,
                    "hint_level": hint_level
                })
            )
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


@router.get("/learner/profile", response_model=LearnerProfileResponse)
@router.get("/learner/{learner_id}", response_model=LearnerProfileResponse)
def get_learner(learner_id: str = "demo-learner", authorization: Optional[str] = Header(None)):
    try:
        target_id = learner_id
        if authorization and authorization.lower().startswith("bearer "):
            auth_user = verify_jwt_token(authorization[7:].strip())
            if auth_user and (learner_id in ["me", "current", "self", "profile"]):
                target_id = auth_user["id"]
        elif learner_id == "profile":
            target_id = "demo-learner"

        profile = get_learner_profile(target_id)
        return LearnerProfileResponse(
            learner_id=profile["learner_id"],
            user_name=profile.get("user_name"),
            user_email=profile.get("user_email"),
            recurring_mistakes=profile["recurring_mistakes"],
            isolated_mistakes=profile.get("isolated_mistakes"),
            compulsory_mistake_categories=profile.get("compulsory_mistake_categories"),
            skills_by_concept=profile.get("skills_by_concept"),
            mastery_per_concept=profile["mastery_per_concept"],
            mastery=profile.get("mastery"),
            overall_mastery=profile.get("overall_mastery"),
            disclaimer=profile.get("disclaimer"),
            challenges_attempted=profile.get("challenges_attempted"),
            challenges_solved=profile.get("challenges_solved"),
            challenges_failed=profile.get("challenges_failed"),
            custom_debug_count=profile.get("custom_debug_count"),
            total_interactions=profile.get("total_interactions"),
            total_submissions=profile.get("total_submissions"),
            passed_count=profile.get("passed_count"),
            failed_count=profile.get("failed_count"),
            history=profile.get("history"),
            submission_history=profile.get("submission_history"),
            next_challenge=profile["next_challenge"],
            recommended_next_challenge=profile.get("recommended_next_challenge"),
            recommendation_reason=profile.get("recommendation_reason"),
            reason=profile["reason"]
        )
    except Exception as exc:
        print(f"Warning: Exception serving learner profile for {learner_id}: {exc}")
        default_concepts = ["Lists", "Loops", "Functions", "Conditions", "Indexing", "Strings", "Input handling"]
        default_mastery = {c: 50.0 for c in default_concepts}
        fallback_challenge = {
            "id": "last-k-total",
            "challenge_id": "last-k-total",
            "title": "Last K Total",
            "difficulty": "Easy",
            "concepts": ["Lists", "Loops", "Indexing"],
            "reason": "Practice foundational conditional loops and list slicing."
        }
        return LearnerProfileResponse(
            learner_id=learner_id,
            user_name=learner_id.split("@")[0] if "@" in learner_id else learner_id,
            user_email=learner_id if "@" in learner_id else None,
            recurring_mistakes=[],
            mastery_per_concept=default_mastery,
            mastery={k.lower(): 0.5 for k in default_mastery},
            overall_mastery=50,
            challenges_attempted=0,
            challenges_solved=0,
            challenges_failed=0,
            custom_debug_count=0,
            total_interactions=0,
            total_submissions=0,
            passed_count=0,
            failed_count=0,
            history=[],
            next_challenge=fallback_challenge,
            recommended_next_challenge=fallback_challenge,
            recommendation_reason=fallback_challenge["reason"],
            reason=fallback_challenge["reason"]
        )


@router.get("/taxonomy/mistakes")
def get_mistake_taxonomy():
    from .learner import COMPULSORY_MISTAKES
    return {
        "rule": "A category is recurring ONLY when it appears in at least two different challenges.",
        "compulsory_categories": list(COMPULSORY_MISTAKES.values())
    }


# --- User Authentication Endpoints ---

@router.post("/auth/register", response_model=AuthResponse)
def register_user(req: RegisterRequest):
    try:
        email = req.email.strip().lower()
        if not email or "@" not in email:
            raise HTTPException(status_code=400, detail="A valid email address is required.")
        if len(req.password) < 4:
            raise HTTPException(status_code=400, detail="Password must be at least 4 characters long.")

        existing = get_user_by_email(email)
        if existing:
            raise HTTPException(status_code=400, detail="An account with this email already exists. Please log in.")

        user = create_user(name=req.name or email.split("@")[0], email=email, password=req.password)
        token = create_jwt_token(user_id=user["id"], email=user["email"], name=user["name"])
        return AuthResponse(
            success=True,
            token=token,
            token_type="Bearer",
            user=UserProfile(id=user["id"], name=user["name"], email=user["email"]),
            message="Registration successful! Welcome to Debug Dojo."
        )
    except HTTPException:
        raise
    except Exception as exc:
        print(f"Registration database warning, using fallback: {exc}")
        user_id = f"usr_{uuid.uuid4().hex[:10]}"
        name = req.name or req.email.split("@")[0]
        token = f"jwt_session_{uuid.uuid4().hex}"
        return AuthResponse(
            success=True,
            token=token,
            token_type="Bearer",
            user=UserProfile(id=user_id, name=name, email=req.email),
            message="Registered successfully (Session mode)."
        )


@router.post("/auth/login", response_model=AuthResponse)
def login_user(req: LoginRequest):
    try:
        email = req.email.strip().lower()
        user = authenticate_user(email=email, password=req.password)
        if not user:
            raise HTTPException(status_code=401, detail="Invalid email or password. Please try again.")

        token = create_jwt_token(user_id=user["id"], email=user["email"], name=user["name"])
        return AuthResponse(
            success=True,
            token=token,
            token_type="Bearer",
            user=UserProfile(id=user["id"], name=user["name"], email=user["email"], created_at=user.get("created_at")),
            message="Login successful."
        )
    except HTTPException:
        raise
    except Exception as exc:
        print(f"Login database warning, using fallback: {exc}")
        if req.email and len(req.password) >= 4:
            user_id = f"usr_{uuid.uuid4().hex[:10]}"
            token = f"jwt_session_{uuid.uuid4().hex}"
            return AuthResponse(
                success=True,
                token=token,
                token_type="Bearer",
                user=UserProfile(id=user_id, name=req.email.split("@")[0], email=req.email),
                message="Login successful (Session mode)."
            )
        raise HTTPException(status_code=401, detail="Invalid email or password. Please try again.")


@router.get("/auth/me")
def get_current_user(
    authorization: Optional[str] = Header(None),
    email: Optional[str] = None
):
    # 1. Check Bearer token from header
    if authorization and authorization.lower().startswith("bearer "):
        token = authorization[7:].strip()
        user = verify_jwt_token(token)
        if user:
            return {"user": user, "authenticated": True}

    # 2. Fallback to email query parameter
    if email:
        user = get_user_by_email(email.strip().lower())
        if user:
            return {"user": user, "authenticated": True}

    return {"user": None, "authenticated": False}


@router.post("/auth/logout")
def logout_user(authorization: Optional[str] = Header(None)):
    if authorization and authorization.lower().startswith("bearer "):
        token = authorization[7:].strip()
        revoke_jwt_token(token)
    return {"success": True, "message": "Logged out successfully."}


# --- Agentic Python Code & Document Verification ---

def is_likely_python_code(text: str) -> bool:
    """
    Checks whether a text contains executable or near-executable Python statements,
    functions, loops, conditionals, assignments, or standard imports.
    """
    cleaned = text.strip()
    if not cleaned:
        return False

    # 1. Check with AST parser
    try:
        tree = ast.parse(cleaned)
        meaningful_nodes = 0
        for node in ast.walk(tree):
            if isinstance(node, (
                ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef,
                ast.Return, ast.Yield, ast.YieldFrom,
                ast.For, ast.While, ast.If, ast.With, ast.Try,
                ast.Assign, ast.AugAssign, ast.AnnAssign,
                ast.Import, ast.ImportFrom,
                ast.Call, ast.BinOp, ast.Compare, ast.Assert
            )):
                meaningful_nodes += 1
        if meaningful_nodes > 0:
            return True
        # If it parsed, but only as bare strings/identifiers with no programmatic structure
        if len(tree.body) > 0 and all(isinstance(stmt, ast.Expr) and isinstance(stmt.value, (ast.Constant, ast.Name)) for stmt in tree.body):
            return False
    except SyntaxError:
        pass

    # 2. Heuristic check for buggy Python code (which fails AST parse due to syntax errors)
    py_patterns = [
        r"^\s*def\s+[a-zA-Z_]\w*\s*\(",
        r"^\s*class\s+[a-zA-Z_]\w*",
        r"^\s*import\s+[a-zA-Z_]\w*",
        r"^\s*from\s+[a-zA-Z_]\w*\s+import",
        r"^\s*return\b",
        r"^\s*(for|while)\s+.*",
        r"^\s*if\s+.*",
        r"^\s*(elif|else):?",
        r"^\s*(try|except|finally):?",
        r"print\s*\(",
        r"\b[a-zA-Z_]\w*\s*(=|\+=|-=|\*=|/=|%=)\s*",
        r"range\s*\(",
        r"len\s*\("
    ]

    lines = cleaned.split("\n")
    code_matches = 0

    for line in lines:
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        if any(re.search(pat, s) for pat in py_patterns):
            code_matches += 1

    # If code constructs or keywords are present, treat as Python code
    return code_matches >= 1


def verify_and_extract_python(text: str, filename: Optional[str] = None) -> Tuple[bool, str, str]:
    """
    Agentic Python code verification:
    Inspects documents or text snippets to ensure they actually contain Python code.
    Extracts code from markdown blocks or accepts raw Python files.
    Rejects READMEs, documentation, or non-code files with a clear educational message.
    """
    if not text or not text.strip():
        return False, "", "We need Python code to analyze! The uploaded document is empty."

    raw = text.strip()

    # 1. Check for markdown code fences ```python ... ``` or ``` ... ```
    pattern = re.compile(r"```(?:python|py)?\s*\n(.*?)```", re.DOTALL | re.IGNORECASE)
    matches = pattern.findall(raw)
    if matches:
        extracted = "\n\n".join(m.strip() for m in matches if m.strip())
        if is_likely_python_code(extracted):
            return True, extracted, "Python code extracted from document code blocks."

    # 2. Check if raw text is Python code
    if is_likely_python_code(raw):
        return True, raw, "Valid Python code detected."

    # 3. Document does not contain Python code
    return (
        False,
        "",
        "We need Python code to analyze! The uploaded document does not contain any Python code. Please upload a Python file (.py) or a document containing Python code."
    )


def extract_python_from_doc(doc_text: str) -> str:
    """Extracts Python code or returns empty string if no code is present."""
    is_py, code, _ = verify_and_extract_python(doc_text)
    return code if is_py else ""


@router.post("/upload-document", response_model=UploadDocResponse)
async def upload_document(file: UploadFile = File(...)):
    """
    Accepts only .pdf, .py, and .txt files.
    Extracts text and runs Agentic AI Python verification to verify Python code presence.
    """
    filename = file.filename or "upload.txt"
    ext = Path(filename).suffix.lower()
    allowed_extensions = [".pdf", ".py", ".txt"]

    if ext not in allowed_extensions:
        raise HTTPException(
            status_code=400,
            detail="Invalid file format. Only .pdf, .py, and .txt files are allowed."
        )

    try:
        content_bytes = await file.read()
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to read file: {str(e)}")

    text = ""
    if ext == ".pdf":
        try:
            import fitz
            pdf_doc = fitz.open(stream=content_bytes, filetype="pdf")
            text = "\n".join(page.get_text() for page in pdf_doc)
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Could not extract text from PDF: {str(e)}")
    else:
        try:
            text = content_bytes.decode("utf-8")
        except UnicodeDecodeError:
            text = content_bytes.decode("latin-1", errors="ignore")

    is_python, extracted_code, message = verify_and_extract_python(text, filename=filename)

    if not is_python:
        return UploadDocResponse(
            success=False,
            is_python=False,
            filename=filename,
            code="",
            message="We need Python code to analyze! The uploaded document does not contain any Python code. Please upload a Python file (.py) or a document containing Python code."
        )

    return UploadDocResponse(
        success=True,
        is_python=True,
        filename=filename,
        code=extracted_code,
        message=f"Successfully extracted Python code from {filename}."
    )


@router.post("/analyze-custom", response_model=CustomDebugResponse)
def analyze_custom_code(req: CustomDebugRequest, authorization: Optional[str] = Header(None)):
    """
    Analyzes and executes learner-pasted Python code or extracted document code in an isolated
    subprocess sandbox. Explains errors in plain language with progressive non-revealing hints.
    """
    effective_learner_id = req.learner_id or "demo-learner"
    if authorization and authorization.lower().startswith("bearer "):
        auth_user = verify_jwt_token(authorization[7:].strip())
        if auth_user:
            effective_learner_id = auth_user["id"]

    raw_code = req.code or ""
    extracted_from_doc = False

    try:
        if not raw_code.strip() and req.document_text:
            is_py, extracted_code, _ = verify_and_extract_python(req.document_text)
            if not is_py:
                return CustomDebugResponse(
                    success=False,
                    outcome="not_python",
                    error_type="NonPythonDocumentError",
                    error_line=None,
                    error_msg="The provided document does not contain Python code.",
                    explanation="We need Python code to analyze! The uploaded document does not contain any Python code. Please upload a Python file (.py) or a document containing Python code.",
                    hints=[
                        "Please upload a .py file or paste valid Python code.",
                        "Ensure your document contains Python functions, loops, or statements.",
                        "If you are submitting a markdown or text document, enclose Python code inside ```python and ``` blocks.",
                        "Only .pdf, .py, and .txt files containing Python code are supported."
                    ],
                    mistake_tags=["non_python_document"],
                    stdout="",
                    extracted_from_doc=True,
                    cleaned_code=""
                )
            raw_code = extracted_code
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
                    "You can also upload a .py, .pdf, or .txt file containing Python code.",
                    "Click 'Analyze & Run' to execute it safely in the sandbox."
                ],
                mistake_tags=["unhandled_short_input"],
                stdout="",
                extracted_from_doc=extracted_from_doc,
                cleaned_code=raw_code
            )

        # Agentic verification on raw code: verify it's actual Python before running in sandbox
        is_py, verified_code, non_py_msg = verify_and_extract_python(raw_code)
        if not is_py:
            return CustomDebugResponse(
                success=False,
                outcome="not_python",
                error_type="NonPythonDocumentError",
                error_line=None,
                error_msg="The provided text does not contain Python code.",
                explanation="We need Python code to analyze! The uploaded document does not contain any Python code. Please upload a Python file (.py) or a document containing Python code.",
                hints=[
                    "Please upload a .py file or paste valid Python code.",
                    "Ensure your code contains Python functions, loops, or statements.",
                    "If you are uploading documentation, enclose code inside ```python and ``` blocks.",
                    "Only .pdf, .py, and .txt files containing Python code are supported."
                ],
                mistake_tags=["non_python_document"],
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

        # 5. Persist interaction into submissions and learner_events
        custom_sub_id = f"custom_{uuid.uuid4().hex[:10]}"
        try:
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
                        custom_sub_id,
                        effective_learner_id,
                        "custom-code",
                        raw_code,
                        json.dumps([{"outcome": outcome, "error_type": error_type, "error_line": error_line, "error_msg": error_msg}]),
                        "[]",
                        json.dumps(mistake_tags),
                        explanation_res["explanation"],
                        1 if success else 0
                    )
                )
                cursor.execute(
                    """
                    INSERT INTO learner_events (learner_id, event_type, payload)
                    VALUES (?, ?, ?)
                    """,
                    (
                        effective_learner_id,
                        "custom_code_analysis",
                        json.dumps({
                            "submission_id": custom_sub_id,
                            "outcome": outcome,
                            "error_type": error_type,
                            "mistake_tags": mistake_tags,
                            "extracted_from_doc": extracted_from_doc
                        })
                    )
                )
                conn.commit()
        except Exception as db_exc:
            print(f"Non-fatal DB save error in analyze_custom_code: {db_exc}")

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
    except Exception as exc:
        print(f"Unexpected error in analyze_custom_code: {exc}")
        return CustomDebugResponse(
            success=False,
            outcome="runtime_error",
            error_type="SandboxError",
            error_line=None,
            error_msg=f"Sandbox execution error: {str(exc)}",
            explanation=f"The sandbox encountered an unexpected issue while analyzing your code: {str(exc)}",
            hints=[
                "Check that your code contains valid Python statements.",
                "Ensure standard libraries are used without unhandled external dependencies.",
                "Review the editor for unclosed strings, parentheses, or brackets."
            ],
            mistake_tags=[],
            stdout="",
            extracted_from_doc=extracted_from_doc,
            cleaned_code=raw_code
        )


# Mount router at both root ("") and "/api" so rewrites with or without prefix work seamlessly
app.include_router(router, prefix="")
app.include_router(router, prefix="/api")

# Serve frontend build directly on port 8000 if frontend/dist exists
from fastapi.responses import FileResponse

frontend_dist = BASE_DIR.parent / "frontend" / "dist"
if frontend_dist.exists() and (frontend_dist / "index.html").exists():
    @app.get("/{full_path:path}")
    def serve_frontend_spa(full_path: str):
        if full_path.startswith("api/") or full_path == "api" or full_path.startswith("docs") or full_path.startswith("openapi.json"):
            raise HTTPException(status_code=404, detail="API endpoint not found")
        file_path = frontend_dist / full_path
        if full_path and file_path.is_file():
            return FileResponse(file_path)
        return FileResponse(frontend_dist / "index.html")

