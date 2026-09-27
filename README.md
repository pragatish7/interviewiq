# InterviewIQ — AI Mock Interview Performance Analyzer

Analyze mock interviews two ways:

1. **Video Upload** — upload a recorded mock interview; the app transcribes it
   (Whisper), analyzes speech delivery, content, and non-verbal signals, and
   produces a scored report with coaching feedback.
2. **Live AI Interview** — answer dataset questions live through your
   microphone; each spoken answer is transcribed in the browser and scored
   against graded reference answers, ending in a full session report.

Both workflows are backed by an ML answer-scoring model trained on graded
interview answers (see [ML pipeline](#ml-pipeline)).

## Project structure

```
backend/          FastAPI app (routes, services, ML bridge, models)
frontend/         React + Vite app (Red Noir dark theme)
training/         Reproducible ML training pipeline
  preprocess.py        videos -> transcripts (resumable, faster-whisper)
  extract_features.py  transcripts + labeled CSV -> processed CSVs
  train.py             train / evaluate / save the model
  evaluate.py          standalone held-out evaluation
models/           Trained artifacts (gitignored; regenerate via training/)
scripts/          Static frontend server with /api proxy
data/             Datasets + processed outputs (gitignored)
```

## Quick start

Prerequisites: Python 3.11+ and Node.js (for building the frontend once).

```bash
# 1. Backend
cd backend
python -m venv ../.venv
../.venv/Scripts/python -m pip install -r requirements.txt   # Windows
../.venv/bin/python -m pip install -r requirements.txt       # macOS/Linux

# 2. Frontend (build once)
cd ../frontend
npm install
npm run build

# 3. Run
cd ..
.venv/Scripts/python -m uvicorn app.main:app --app-dir backend --port 8000
.venv/Scripts/python -m scripts.serve_frontend 3001          # serves dist + /api proxy
```

Open **http://localhost:3001**. API docs at **http://localhost:8000/docs**.

On Windows you can also double-click `START_APP.bat` (and `STOP_APP.bat` to stop).

> The trained model binaries are not committed. On first backend start the
> legacy model self-trains from synthetic data; for the real model run
> `python -m training.train` (needs `data/mock_interview_dataset_test.csv`).

## ML pipeline

**Honesty note:** the 1,514 interview videos in the original dataset ship
**without any labels** (no scores, questions, or metadata). The pipeline
transcribes and featurizes them but never invents scores. The supervised model
trains on the 750 graded answers in the mock-interview dataset
(`data/mock_interview_dataset_test.csv`: 150 questions × 5 quality grades ×
10 categories).

```bash
# Transcribe videos (resumable — rerun anytime; skips done work)
python -m training.preprocess

# Build feature CSVs (labeled training set + video annotation template)
python -m training.extract_features

# Train, evaluate (grouped split by question — no leakage), save artifacts
python -m training.train

# Independent held-out evaluation of the saved model
python -m training.evaluate
```

Latest run (`models/training_report.json`): **Ridge regression, test MAE 2.28,
RMSE 2.94, R² 0.9896** on held-out question groups; per-grade predictions are
monotonic (Very Poor → 15.4 … Very Good → 94.8).

Feature parity is guaranteed by a single feature module
(`backend/app/ml/answer_features.py`) used by both training and the live
interview; the live interview surfaces the trained model's estimate as a
reference-only badge (the rule-based rubric score stays authoritative), and
`GET /api/live-interviews/model-info` exposes the model's provenance.

Videos without scores land in `data/processed/annotation_template.csv`
(`video,question,candidate_answer,score`) — fill real scores and rerun
`training.train` to include them.

## Notes

- Camera/mic for the Live Interview work in real Chrome on
  `http://localhost:3001` (secure-origin rule); the embedded preview webview
  falls back to Type mode by design.
- The SQLite DB (`data/interviewiq.db`) and uploaded videos are machine-local
  and gitignored.
