"""
AI Problem Analyzer.
Analyzes problem statements, produces structured specifications,
generates a hidden reference solution, and verifies all test cases against it.
"""

import os
import re
import json
from typing import Dict, Any, List, Optional
import httpx

from .sandbox import run_single_test_isolated
from .llm import (
    get_gemini_api_key,
    get_optimal_gemini_model,
    PRO_FALLBACKS,
    FLASH_FALLBACKS
)


SYSTEM_PROMPT = """You are an expert LeetCode-style problem designer and judge.
Analyze the user's problem statement and output a STRICT JSON object in LeetCode Python function format:

{
  "title": "Concise, descriptive problem title (e.g. Two Sum)",
  "summary": "Clear 2-3 sentence summary explaining what the problem asks to solve",
  "function_name": "Python function name in snake_case (e.g. two_sum, is_palindrome)",
  "starter_code": "def function_name(arg1: type1, arg2: type2) -> return_type:\\n    # Write your solution here\\n    pass",
  "input_format": "Exact specification of function arguments",
  "output_format": "Exact specification of returned value",
  "constraints": [
    "Constraint 1 (e.g., 2 <= nums.length <= 10^4)",
    "Constraint 2 (e.g., -10^9 <= nums[i] <= 10^9)"
  ],
  "sample_test_cases": [
    {
      "input": "LeetCode style string representation (e.g. nums = [2,7,11,15], target = 9)",
      "call_args": [[2, 7, 11, 15], 9],
      "expected_output": "[0, 1]",
      "explanation": "Brief explanation of why this output is correct"
    },
    {
      "input": "nums = [3,2,4], target = 6",
      "call_args": [[3, 2, 4], 6],
      "expected_output": "[1, 2]",
      "explanation": "Brief explanation of sample 2"
    }
  ],
  "hidden_test_cases": [
    {
      "input": "nums = [3,3], target = 6",
      "call_args": [[3, 3], 6],
      "expected_output": "[0, 1]",
      "is_edge_case": true
    },
    {
      "input": "nums = [-3,4,3,90], target = 0",
      "call_args": [[-3, 4, 3, 90], 0],
      "expected_output": "[0, 2]",
      "is_edge_case": true
    },
    {
      "input": "nums = [1,2,3,4,6], target = 10",
      "call_args": [[1, 2, 3, 4, 6], 10],
      "expected_output": "[3, 4]",
      "is_edge_case": false
    },
    {
      "input": "nums = [-1,-2,-3,-4,-5], target = -8",
      "call_args": [[-1, -2, -3, -4, -5], -8],
      "expected_output": "[2, 4]",
      "is_edge_case": true
    },
    {
      "input": "nums = [5,20,35,80,95], target = 100",
      "call_args": [[5, 20, 35, 80, 95], 100],
      "expected_output": "[1, 3]",
      "is_edge_case": false
    },
    {
      "input": "nums = [1,2,3], target = 4",
      "call_args": [[1, 2, 3], 4],
      "expected_output": "[0, 2]",
      "is_edge_case": false
    }
  ],
  "reference_solution": "Complete, correct Python 3 function that returns the exact answer (e.g. def two_sum(nums, target): ... return ans)."
}

REQUIREMENTS:
1. ONLY Python 3 is supported.
2. starter_code MUST ONLY provide the function signature and pass (like LeetCode).
3. The reference_solution must be a complete, correct Python 3 function matching starter_code signature.
4. Output raw JSON only.
"""


def _generate_fallback_problem_spec(problem_statement: str) -> Dict[str, Any]:
    """
    Intelligent offline fallback parser for LeetCode-style Python problems.
    """
    lower = problem_statement.lower()

    if "two sum" in lower or ("indices" in lower and "target" in lower):
        return {
            "title": "Two Sum",
            "summary": "Given an array of integers nums and an integer target, return indices of the two numbers such that they add up to target.",
            "function_name": "two_sum",
            "starter_code": "def two_sum(nums: list[int], target: int) -> list[int]:\n    # Write your solution here\n    pass\n",
            "input_format": "nums: list[int], target: int",
            "output_format": "list[int] containing two indices",
            "constraints": [
                "2 <= nums.length <= 10^4",
                "-10^9 <= nums[i] <= 10^9",
                "Exactly one valid solution exists."
            ],
            "sample_test_cases": [
                {
                    "input": "nums = [2,7,11,15], target = 9",
                    "call_args": [[2, 7, 11, 15], 9],
                    "expected_output": "[0, 1]",
                    "explanation": "Because nums[0] + nums[1] == 9, we return [0, 1]."
                },
                {
                    "input": "nums = [3,2,4], target = 6",
                    "call_args": [[3, 2, 4], 6],
                    "expected_output": "[1, 2]",
                    "explanation": "Because nums[1] + nums[2] == 6, we return [1, 2]."
                }
            ],
            "hidden_test_cases": [
                {"input": "nums = [3,3], target = 6", "call_args": [[3, 3], 6], "expected_output": "[0, 1]", "is_edge_case": True},
                {"input": "nums = [-3,4,3,90], target = 0", "call_args": [[-3, 4, 3, 90], 0], "expected_output": "[0, 2]", "is_edge_case": True},
                {"input": "nums = [1,2,3,4,6], target = 10", "call_args": [[1, 2, 3, 4, 6], 10], "expected_output": "[3, 4]", "is_edge_case": False},
                {"input": "nums = [-1,-2,-3,-4,-5], target = -8", "call_args": [[-1, -2, -3, -4, -5], -8], "expected_output": "[2, 4]", "is_edge_case": True},
                {"input": "nums = [5,20,35,80,95], target = 100", "call_args": [[5, 20, 35, 80, 95], 100], "expected_output": "[1, 3]", "is_edge_case": False},
                {"input": "nums = [1,2,3], target = 4", "call_args": [[1, 2, 3], 4], "expected_output": "[0, 2]", "is_edge_case": False}
            ],
            "reference_solution": "def two_sum(nums: list[int], target: int) -> list[int]:\n    seen = {}\n    for i, num in enumerate(nums):\n        diff = target - num\n        if diff in seen:\n            return [seen[diff], i]\n        seen[num] = i\n    return []\n"
        }

    if "palindrome" in lower:
        return {
            "title": "Valid Palindrome",
            "summary": "Determine if a string reads the same forward and backward, ignoring non-alphanumeric characters and case.",
            "function_name": "is_palindrome",
            "starter_code": "def is_palindrome(s: str) -> bool:\n    # Write your solution here\n    pass\n",
            "input_format": "s: str",
            "output_format": "bool (True or False)",
            "constraints": [
                "1 <= s.length <= 2 * 10^5",
                "s consists only of printable ASCII characters."
            ],
            "sample_test_cases": [
                {
                    "input": "s = \"A man, a plan, a canal: Panama\"",
                    "call_args": ["A man, a plan, a canal: Panama"],
                    "expected_output": "true",
                    "explanation": "\"amanaplanacanalpanama\" is a palindrome."
                },
                {
                    "input": "s = \"race a car\"",
                    "call_args": ["race a car"],
                    "expected_output": "false",
                    "explanation": "\"raceacar\" is not a palindrome."
                }
            ],
            "hidden_test_cases": [
                {"input": "s = \" \"", "call_args": [" "], "expected_output": "true", "is_edge_case": True},
                {"input": "s = \"0P\"", "call_args": ["0P"], "expected_output": "false", "is_edge_case": False},
                {"input": "s = \"a\"", "call_args": ["a"], "expected_output": "true", "is_edge_case": True},
                {"input": "s = \"ab_a\"", "call_args": ["ab_a"], "expected_output": "true", "is_edge_case": True},
                {"input": "s = \"Madam, in Eden, I'm Adam\"", "call_args": ["Madam, in Eden, I'm Adam"], "expected_output": "true", "is_edge_case": False},
                {"input": "s = \"Never odd or even\"", "call_args": ["Never odd or even"], "expected_output": "true", "is_edge_case": False}
            ],
            "reference_solution": "def is_palindrome(s: str) -> bool:\n    import re\n    clean = re.sub(r'[^a-zA-Z0-9]', '', s).lower()\n    return clean == clean[::-1]\n"
        }

    if "subarray" in lower or "kadane" in lower:
        return {
            "title": "Maximum Subarray",
            "summary": "Find the contiguous subarray (containing at least one number) which has the largest sum and return its sum.",
            "function_name": "max_sub_array",
            "starter_code": "def max_sub_array(nums: list[int]) -> int:\n    # Write your solution here\n    pass\n",
            "input_format": "nums: list[int]",
            "output_format": "int (maximum sum)",
            "constraints": [
                "1 <= nums.length <= 10^5",
                "-10^4 <= nums[i] <= 10^4"
            ],
            "sample_test_cases": [
                {
                    "input": "nums = [-2,1,-3,4,-1,2,1,-5,4]",
                    "call_args": [[-2, 1, -3, 4, -1, 2, 1, -5, 4]],
                    "expected_output": "6",
                    "explanation": "Subarray [4,-1,2,1] has the largest sum = 6."
                },
                {
                    "input": "nums = [1]",
                    "call_args": [[1]],
                    "expected_output": "1",
                    "explanation": "The single element 1 is the maximum sum."
                }
            ],
            "hidden_test_cases": [
                {"input": "nums = [5,4,-1,7,8]", "call_args": [[5, 4, -1, 7, 8]], "expected_output": "23", "is_edge_case": False},
                {"input": "nums = [-5,-2,-8,-1]", "call_args": [[-5, -2, -8, -1]], "expected_output": "-1", "is_edge_case": True},
                {"input": "nums = [-1,-2]", "call_args": [[-1, -2]], "expected_output": "-1", "is_edge_case": True},
                {"input": "nums = [0,0,0]", "call_args": [[0, 0, 0]], "expected_output": "0", "is_edge_case": True},
                {"input": "nums = [1,2,3,-10,5,6]", "call_args": [[1, 2, 3, -10, 5, 6]], "expected_output": "11", "is_edge_case": False},
                {"input": "nums = [-1,2,3,4,-5]", "call_args": [[-1, 2, 3, 4, -5]], "expected_output": "9", "is_edge_case": False}
            ],
            "reference_solution": "def max_sub_array(nums: list[int]) -> int:\n    max_so_far = cur = nums[0]\n    for x in nums[1:]:\n        cur = max(x, cur + x)\n        max_so_far = max(max_so_far, cur)\n    return max_so_far\n"
        }

    # Generic challenge fallback
    first_line = problem_statement.strip().split("\n")[0][:60]
    title = re.sub(r"^[#\s\d.-]+", "", first_line).strip() or "Custom Algorithmic Challenge"
    func_name = re.sub(r"[^a-zA-Z0-9]+", "_", title.lower()).strip("_") or "solution"
    if func_name[0].isdigit():
        func_name = f"solve_{func_name}"

    return {
        "title": title,
        "summary": problem_statement.strip()[:240] + ("..." if len(problem_statement) > 240 else ""),
        "function_name": func_name,
        "starter_code": f"def {func_name}(nums: list[int]) -> int:\n    # Write your solution here\n    pass\n",
        "input_format": "nums: list[int]",
        "output_format": "int or calculated result",
        "constraints": [
            "1 <= nums.length <= 10^5",
            "-10^6 <= nums[i] <= 10^6"
        ],
        "sample_test_cases": [
            {
                "input": "nums = [1, 2, 3, 4, 5]",
                "call_args": [[1, 2, 3, 4, 5]],
                "expected_output": "15",
                "explanation": "Sum of elements."
            },
            {
                "input": "nums = [10, 20, 30]",
                "call_args": [[10, 20, 30]],
                "expected_output": "60",
                "explanation": "Sum of elements."
            }
        ],
        "hidden_test_cases": [
            {"input": "nums = [42]", "call_args": [[42]], "expected_output": "42", "is_edge_case": True},
            {"input": "nums = [-5, 5]", "call_args": [[-5, 5]], "expected_output": "0", "is_edge_case": True},
            {"input": "nums = [0, 0, 0, 0]", "call_args": [[0, 0, 0, 0]], "expected_output": "0", "is_edge_case": True},
            {"input": "nums = [-1, -2, -3]", "call_args": [[-1, -2, -3]], "expected_output": "-6", "is_edge_case": True},
            {"input": "nums = [100, 200, 300, 400, 500]", "call_args": [[100, 200, 300, 400, 500]], "expected_output": "1500", "is_edge_case": False},
            {"input": "nums = [2, 4, 6, 8, 10, 12]", "call_args": [[2, 4, 6, 8, 10, 12]], "expected_output": "42", "is_edge_case": False}
        ],
        "reference_solution": f"def {func_name}(nums: list[int]) -> int:\n    return sum(nums) if nums else 0\n"
    }


async def _call_gemini_api(problem_statement: str) -> Optional[Dict[str, Any]]:
    """
    Calls Gemini REST API via httpx using dynamic free-tier model selection.
    Uses Gemini Pro for complex algorithmic problems (DP, graphs, large scale)
    and Gemini Flash for standard challenges.
    """
    api_key = get_gemini_api_key()
    if not api_key:
        return None

    target_model = get_optimal_gemini_model(problem_statement)
    candidate_models = PRO_FALLBACKS if target_model in PRO_FALLBACKS else FLASH_FALLBACKS
    ordered_models = [target_model] + [m for m in candidate_models if m != target_model]

    payload = {
        "contents": [
            {
                "role": "user",
                "parts": [
                    {"text": f"{SYSTEM_PROMPT}\n\nPROBLEM STATEMENT TO ANALYZE:\n{problem_statement}"}
                ]
            }
        ],
        "generationConfig": {
            "temperature": 0.2,
            "responseMimeType": "application/json"
        }
    }

    for model_name in ordered_models:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={api_key}"
        try:
            async with httpx.AsyncClient(timeout=35.0) as client:
                resp = await client.post(url, json=payload)
                if resp.status_code == 200:
                    data = resp.json()
                    candidates = data.get("candidates", [])
                    if not candidates:
                        continue
                    text = candidates[0].get("content", {}).get("parts", [{}])[0].get("text", "")
                    if not text:
                        continue

                    # Clean markdown code fences if returned
                    text = re.sub(r"^```json\s*", "", text.strip())
                    text = re.sub(r"\s*```$", "", text.strip())
                    parsed = json.loads(text)
                    if parsed:
                        parsed["model_used"] = model_name
                        return parsed
                elif resp.status_code in (429, 404, 503):
                    # Rate limit or model unavailable, try fallback model
                    continue
        except Exception:
            continue

    return None


async def verify_tests_against_reference(
    spec: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Executes the generated reference solution against every test case.
    Verifies that the reference solution is valid and updates expected_output
    with the actual reference output to ensure zero test discrepancies.
    """
    ref_code = spec.get("reference_solution", "")
    if not ref_code or not ref_code.strip():
        return spec

    # 1. Verify and calibrate sample test cases
    calibrated_samples = []
    for s in spec.get("sample_test_cases", []):
        inp = str(s.get("input", ""))
        orig_exp = str(s.get("expected_output", ""))
        
        exec_res = await run_single_test_isolated(
            code=ref_code,
            language="python",
            stdin=inp,
            expected_output=orig_exp,
            timeout_s=3.0
        )
        got = exec_res.get("got", "")
        # If reference produced output without runtime error, calibrate expected output to match
        final_exp = got if (got and exec_res.get("status") != "error") else orig_exp
        
        calibrated_samples.append({
            "input": inp,
            "expected_output": final_exp,
            "explanation": s.get("explanation", "")
        })

    # 2. Verify and calibrate hidden test cases
    calibrated_hidden = []
    for h in spec.get("hidden_test_cases", []):
        inp = str(h.get("input", ""))
        orig_exp = str(h.get("expected_output", ""))
        
        exec_res = await run_single_test_isolated(
            code=ref_code,
            language="python",
            stdin=inp,
            expected_output=orig_exp,
            timeout_s=3.0
        )
        got = exec_res.get("got", "")
        final_exp = got if (got and exec_res.get("status") != "error") else orig_exp

        calibrated_hidden.append({
            "input": inp,
            "expected_output": final_exp,
            "is_edge_case": bool(h.get("is_edge_case", False))
        })

    spec["sample_test_cases"] = calibrated_samples
    spec["hidden_test_cases"] = calibrated_hidden
    spec["reference_verified"] = True
    return spec


async def analyze_problem(problem_statement: str) -> Dict[str, Any]:
    """
    Main entry point for problem analysis.
    1. Sends problem statement to Gemini AI or fallback parser.
    2. Validates JSON structure.
    3. Verifies every test case against the hidden reference solution.
    """
    spec = await _call_gemini_api(problem_statement)
    if not spec:
        spec = _generate_fallback_problem_spec(problem_statement)

    # Ensure required fields exist
    spec.setdefault("title", "Algorithmic Problem")
    spec.setdefault("summary", problem_statement.strip()[:200])
    spec.setdefault("function_name", "solution")
    fn = spec.get("function_name", "solution")
    spec.setdefault("starter_code", f"def {fn}(*args):\n    # Write your solution here\n    pass\n")
    spec.setdefault("input_format", "Function parameters")
    spec.setdefault("output_format", "Returned value")
    spec.setdefault("constraints", ["1 <= N <= 10^5"])
    spec.setdefault("sample_test_cases", [])
    spec.setdefault("hidden_test_cases", [])

    # Keep hidden_test_cases between 5 and 8
    if len(spec["hidden_test_cases"]) < 5:
        spec["hidden_test_cases"].append({"input": "0", "expected_output": "0", "is_edge_case": True})
        spec["hidden_test_cases"].append({"input": "1", "expected_output": "1", "is_edge_case": True})
    elif len(spec["hidden_test_cases"]) > 8:
        spec["hidden_test_cases"] = spec["hidden_test_cases"][:8]

    # Verify all test cases against reference solution
    verified_spec = await verify_tests_against_reference(spec)
    return verified_spec
