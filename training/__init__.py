"""InterviewIQ training pipeline.

Modules:
  common           — shared paths, video discovery, constants
  preprocess       — videos -> transcripts (resumable JSON cache per video)
  extract_features — transcripts + labeled dataset -> processed CSVs
  train            — train/evaluate/save the answer-scoring model
  evaluate         — standalone evaluation report for the saved model

Run the whole chain with:  python training/train.py
"""
