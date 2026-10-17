"""
Worker module: The isolated child process runner.
Learner code runs strictly here under hardened security safeguards and resource limits.
Non-Negotiable Rule 1: Learner code NEVER runs inside the server process.
"""

import sys
import io
import json
import copy
import traceback

MAX_OUTPUT_BYTES = 4096


class OutputLimitExceeded(Exception):
    pass


class CappedStringIO(io.StringIO):
    def __init__(self, max_bytes=MAX_OUTPUT_BYTES):
        super().__init__()
        self.max_bytes = max_bytes
        self.current_bytes = 0

    def write(self, s):
        byte_len = len(s.encode("utf-8", errors="replace"))
        if self.current_bytes + byte_len > self.max_bytes:
            allowed_len = max(0, self.max_bytes - self.current_bytes)
            super().write(s[:allowed_len])
            self.current_bytes = self.max_bytes
            raise OutputLimitExceeded("Output limit exceeded (max 4KB)")
        self.current_bytes += byte_len
        return super().write(s)


def apply_sandbox_guards():
    """Hardened security guards to isolate the child process execution."""
    # 1. Disable network sockets
    try:
        import socket
        def blocked_socket(*args, **kwargs):
            raise PermissionError("Network socket access is disabled in the sandbox.")
        socket.socket = blocked_socket
    except Exception:
        pass

    # 2. Disable process spawning
    try:
        import subprocess
        def blocked_subprocess(*args, **kwargs):
            raise PermissionError("Process spawning is disabled in the sandbox.")
        subprocess.Popen = blocked_subprocess
        subprocess.run = blocked_subprocess
        subprocess.call = blocked_subprocess
        subprocess.check_output = blocked_subprocess
    except Exception:
        pass

    # 3. Disable dangerous OS calls
    try:
        import os
        def blocked_os(*args, **kwargs):
            raise PermissionError("OS system execution is disabled in the sandbox.")
        os.system = blocked_os
        os.popen = blocked_os
        if hasattr(os, "fork"):
            os.fork = blocked_os
        if hasattr(os, "execv"):
            os.execv = blocked_os
    except Exception:
        pass


def run_test_case(code: str, function_name: str, call_args: list, call_kwargs: dict):
    apply_sandbox_guards()

    # Capture stdout and stderr with output capping
    stdout_buffer = CappedStringIO(MAX_OUTPUT_BYTES)
    stderr_buffer = CappedStringIO(MAX_OUTPUT_BYTES)

    old_stdout = sys.stdout
    old_stderr = sys.stderr

    sys.stdout = stdout_buffer
    sys.stderr = stderr_buffer

    # Safe environment
    safe_globals = {
        "__builtins__": __builtins__,
        "__name__": "__main__",
    }

    mutated_input = False
    return_val = None
    output_limit_hit = False
    runtime_error_msg = None

    try:
        # Clone arguments to detect mutation
        try:
            args_before = copy.deepcopy(call_args)
            kwargs_before = copy.deepcopy(call_kwargs)
        except Exception:
            args_before = call_args
            kwargs_before = call_kwargs

        # Execute learner code definition
        exec(code, safe_globals)

        # Locate learner function if specified
        if function_name and function_name != "__main__":
            if function_name not in safe_globals or not callable(safe_globals[function_name]):
                raise NameError(f"Function '{function_name}' was not defined in your code.")

            target_func = safe_globals[function_name]

            # Call learner function
            return_val = target_func(*call_args, **call_kwargs)

        # Detect argument mutation (Rule 5: mutates_input)
        try:
            if call_args != args_before or call_kwargs != kwargs_before:
                mutated_input = True
        except Exception:
            mutated_input = False

        exc_type = None
        exc_line = None

    except OutputLimitExceeded:
        output_limit_hit = True
        runtime_error_msg = "Runtime error: Output limit exceeded (max 4KB)"
        exc_type = "OutputLimitExceeded"
        exc_line = None
    except Exception as exc:
        exc_type = type(exc).__name__
        exc_msg = str(exc)
        runtime_error_msg = f"{exc_type}: {exc_msg}"
        exc_line = getattr(exc, "lineno", None)
        if exc_line is None and exc.__traceback__:
            tb = exc.__traceback__
            while tb:
                if tb.tb_frame.f_code.co_filename == "<string>":
                    exc_line = tb.tb_lineno
                tb = tb.tb_next
    finally:
        sys.stdout = old_stdout
        sys.stderr = old_stderr

    captured_stdout = stdout_buffer.getvalue()
    captured_stderr = stderr_buffer.getvalue()

    return {
        "return_val": return_val,
        "stdout": captured_stdout,
        "stderr": captured_stderr,
        "mutated_input": mutated_input,
        "output_limit_hit": output_limit_hit,
        "runtime_error": runtime_error_msg,
        "error_type": exc_type,
        "error_line": exc_line,
    }


def main():
    if len(sys.argv) < 2:
        # Read from stdin
        raw_payload = sys.stdin.read()
    else:
        # Read from file specified in argument
        with open(sys.argv[1], "r", encoding="utf-8") as f:
            raw_payload = f.read()

    try:
        payload = json.loads(raw_payload)
        code = payload.get("code", "")
        function_name = payload.get("function_name", "")
        call_args = payload.get("args", [])
        call_kwargs = payload.get("kwargs", {})

        result = run_test_case(code, function_name, call_args, call_kwargs)
        print(json.dumps(result, default=str))
    except Exception as e:
        print(json.dumps({
            "return_val": None,
            "stdout": "",
            "stderr": "",
            "mutated_input": False,
            "output_limit_hit": False,
            "runtime_error": f"Fatal worker error: {str(e)}"
        }))


if __name__ == "__main__":
    main()
