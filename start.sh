#!/bin/bash
echo "=========================================="
echo "  InterviewIQ - Starting Application"
echo "=========================================="
echo ""

# Install backend dependencies
echo "[1/4] Installing backend dependencies..."
cd backend
pip install -r requirements.txt -q 2>/dev/null
cd ..

# Install frontend dependencies
echo "[2/4] Installing frontend dependencies..."
cd frontend
npm install --silent 2>/dev/null
cd ..

# Train ML model if needed
echo "[3/4] Checking ML model..."
cd backend
python -c "
import os
model_path = os.path.join('..', 'models', 'model.pkl')
if not os.path.exists(model_path):
    print('  Training ML model on synthetic data...')
    from app.ml.train import train_and_evaluate
    train_and_evaluate()
    print('  Model trained successfully!')
else:
    print('  ML model found.')
" 2>/dev/null
cd ..

# Start servers
echo "[4/4] Starting servers..."
echo ""
echo "Backend: http://localhost:8000"
echo "Frontend: http://localhost:3000"
echo ""

# Start backend
cd backend
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 &
BACKEND_PID=$!
cd ..

# Start frontend
cd frontend
npm run dev &
FRONTEND_PID=$!
cd ..

echo ""
echo "=========================================="
echo "  InterviewIQ is running!"
echo "  Open http://localhost:3000 in browser"
echo "=========================================="

# Wait for both
wait $BACKEND_PID $FRONTEND_PID
