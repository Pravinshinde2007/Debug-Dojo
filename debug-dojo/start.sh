#!/usr/bin/env bash
# ==============================================================================
# Debug Dojo — One-command startup script
# Starts FastAPI backend (port 8000) and Vite frontend (port 5173) together
# ==============================================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "🥋 Starting Debug Dojo..."

# 1. Locate working Python executable
PYTHON_CMD=""
CANDIDATES=("py -3" "py" "python3" "python" "/c/Users/Admin/AppData/Local/Python/bin/python.exe")

for cmd in "${CANDIDATES[@]}"; do
    if $cmd --version &>/dev/null; then
        PYTHON_CMD="$cmd"
        break
    fi
done

if [ -z "$PYTHON_CMD" ]; then
    echo "❌ Error: Working Python 3.11+ executable not found."
    exit 1
fi

echo "✓ Using Python: $($PYTHON_CMD --version 2>&1)"

# 2. Check Backend Dependencies
if [ -f "backend/requirements.txt" ]; then
    echo "📦 Checking backend dependencies..."
    $PYTHON_CMD -m pip install -q -r backend/requirements.txt || true
fi

# 3. Check Frontend Dependencies
if [ ! -d "frontend/node_modules" ]; then
    echo "📦 Installing frontend dependencies..."
    (cd frontend && npm install)
fi

# 4. Cleanup on Exit
BACKEND_PID=""
FRONTEND_PID=""

cleanup() {
    echo ""
    echo "🥋 Shutting down Debug Dojo..."
    if [ -n "$BACKEND_PID" ]; then
        kill "$BACKEND_PID" 2>/dev/null || true
    fi
    if [ -n "$FRONTEND_PID" ]; then
        kill "$FRONTEND_PID" 2>/dev/null || true
    fi
    exit 0
}

trap cleanup INT TERM EXIT

# 5. Start Backend Server
echo "🚀 Starting Backend on http://localhost:8000..."
(
    cd backend
    PYTHONPATH=. $PYTHON_CMD -m uvicorn app.main:app --host 0.0.0.0 --port 8000
) &
BACKEND_PID=$!

# 6. Start Frontend Dev Server
echo "🚀 Starting Frontend on http://localhost:5173..."
(
    cd frontend
    npm run dev -- --host 0.0.0.0 --port 5173
) &
FRONTEND_PID=$!

echo ""
echo "=========================================================="
echo "🥋 Debug Dojo is live!"
echo "   Frontend UI:  http://localhost:5173"
echo "   Backend API:  http://localhost:8000"
echo "   API Docs:     http://localhost:8000/docs"
echo "=========================================================="
echo "Press Ctrl+C to stop both servers."
echo ""

# Keep running
wait
