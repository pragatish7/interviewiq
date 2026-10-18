from sqlalchemy import Column, Integer, String, Float, Text, DateTime, JSON, Boolean, ForeignKey
from sqlalchemy.orm import relationship, declarative_base
from datetime import datetime

Base = declarative_base()


class Interview(Base):
    __tablename__ = "interviews"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(255), default="Interview Session")
    filename = Column(String(500), nullable=False)
    original_filename = Column(String(500), nullable=False)
    file_size = Column(Integer, default=0)
    duration = Column(Float, default=0.0)
    created_at = Column(DateTime, default=datetime.utcnow)
    is_demo = Column(Boolean, default=False)
    status = Column(String(50), default="uploaded")  # uploaded, processing, completed, failed
    error_message = Column(Text, nullable=True)

    # Interview setup
    interview_type = Column(String(50), default="General")
    target_role = Column(String(255), nullable=True)
    experience_level = Column(String(50), nullable=True)
    job_description = Column(Text, nullable=True)

    # Scores
    overall_score = Column(Float, nullable=True)
    communication_score = Column(Float, nullable=True)
    answer_quality_score = Column(Float, nullable=True)
    clarity_score = Column(Float, nullable=True)
    fluency_score = Column(Float, nullable=True)
    speaking_pace_score = Column(Float, nullable=True)
    confidence_score = Column(Float, nullable=True)
    vocabulary_score = Column(Float, nullable=True)
    relevance_score = Column(Float, nullable=True)
    professionalism_score = Column(Float, nullable=True)
    nonverbal_score = Column(Float, nullable=True)
    star_score = Column(Float, nullable=True)

    # Speech metrics
    words_per_minute = Column(Float, nullable=True)
    filler_count = Column(Integer, nullable=True)
    filler_rate = Column(Float, nullable=True)
    pause_count = Column(Integer, nullable=True)
    avg_pause_duration = Column(Float, nullable=True)
    speech_duration = Column(Float, nullable=True)
    total_words = Column(Integer, nullable=True)
    total_sentences = Column(Integer, nullable=True)
    vocabulary_diversity = Column(Float, nullable=True)
    repetition_rate = Column(Float, nullable=True)
    sentiment_score = Column(Float, nullable=True)

    # NLP metrics
    keyword_density = Column(Float, nullable=True)
    relevance_metric = Column(Float, nullable=True)
    technical_terms_count = Column(Integer, default=0)

    # Video metrics
    face_visibility = Column(Float, nullable=True)
    camera_presence = Column(Float, nullable=True)
    head_movement_score = Column(Float, nullable=True)
    framing_score = Column(Float, nullable=True)

    # ML
    ml_predicted_score = Column(Float, nullable=True)
    ml_confidence = Column(Float, nullable=True)

    # JSON fields
    transcript = Column(Text, nullable=True)
    detailed_scores = Column(JSON, nullable=True)
    timeline_events = Column(JSON, nullable=True)
    qa_analysis = Column(JSON, nullable=True)
    coaching_feedback = Column(JSON, nullable=True)
    filler_words_detail = Column(JSON, nullable=True)
    improvement_plan = Column(JSON, nullable=True)
    ml_feature_importance = Column(JSON, nullable=True)
    question_categories = Column(JSON, nullable=True)
    nonverbal_detail = Column(JSON, nullable=True)
    speech_segments = Column(JSON, nullable=True)
    nlp_features = Column(JSON, nullable=True)

    # Relationships
    answers = relationship("AnswerAnalysis", back_populates="interview", cascade="all, delete-orphan")


class AnswerAnalysis(Base):
    __tablename__ = "answer_analyses"

    id = Column(Integer, primary_key=True, index=True)
    interview_id = Column(Integer, ForeignKey("interviews.id"), nullable=False)
    question_index = Column(Integer, nullable=False)
    question_text = Column(Text, nullable=True)
    question_category = Column(String(50), nullable=True)
    answer_text = Column(Text, nullable=True)
    timestamp_start = Column(Float, nullable=True)
    timestamp_end = Column(Float, nullable=True)

    # Scores
    relevance_score = Column(Float, nullable=True)
    completeness_score = Column(Float, nullable=True)
    clarity_score = Column(Float, nullable=True)
    conciseness_score = Column(Float, nullable=True)
    specificity_score = Column(Float, nullable=True)
    structure_score = Column(Float, nullable=True)
    overall_answer_score = Column(Float, nullable=True)

    # STAR
    has_situation = Column(Boolean, default=False)
    has_task = Column(Boolean, default=False)
    has_action = Column(Boolean, default=False)
    has_result = Column(Boolean, default=False)
    star_score = Column(Float, nullable=True)

    # Feedback
    strengths = Column(JSON, nullable=True)
    missing_elements = Column(JSON, nullable=True)
    suggested_improvement = Column(Text, nullable=True)

    interview = relationship("Interview", back_populates="answers")


class ProgressRecord(Base):
    __tablename__ = "progress_records"

    id = Column(Integer, primary_key=True, index=True)
    interview_id = Column(Integer, ForeignKey("interviews.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    overall_score = Column(Float, nullable=True)
    communication_score = Column(Float, nullable=True)
    filler_rate = Column(Float, nullable=True)
    pace = Column(Float, nullable=True)
    answer_quality_score = Column(Float, nullable=True)
    confidence_score = Column(Float, nullable=True)


class LiveInterviewSession(Base):
    """A Live AI Interview session (separate workflow from video uploads).

    Questions come from the shipped mock-interview Q&A dataset. Per-question
    evaluations and the final aggregated report are stored as JSON so the
    existing video-analysis tables remain untouched.
    """

    __tablename__ = "live_interview_sessions"

    id = Column(Integer, primary_key=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    status = Column(String(50), default="in_progress")  # in_progress, completed, abandoned

    # Session configuration
    total_questions = Column(Integer, default=0)
    categories = Column(JSON, nullable=True)  # categories requested by the user
    question_ids = Column(JSON, nullable=True)  # ordered dataset question ids

    # Final aggregated scores (null until completed)
    overall_score = Column(Float, nullable=True)
    technical_score = Column(Float, nullable=True)
    communication_score = Column(Float, nullable=True)
    speech_score = Column(Float, nullable=True)

    # Aggregated speech metrics
    words_per_minute = Column(Float, nullable=True)
    fillers_total = Column(Integer, nullable=True)
    pauses_total = Column(Integer, nullable=True)
    pause_seconds_total = Column(Float, nullable=True)
    duration_s = Column(Float, nullable=True)

    # Results
    results = Column(JSON, nullable=True)  # per-question evaluation dicts
    strengths = Column(JSON, nullable=True)
    areas_for_improvement = Column(JSON, nullable=True)
    overall_feedback = Column(Text, nullable=True)
    transcript = Column(Text, nullable=True)


class CoachSession(Base):
    """An AI Coach conversation (fully independent workflow).

    Messages are stored as a JSON list of {role, content} so the conversation
    can be rehydrated into the coach engine's context on every turn. The
    existing Interview / LiveInterviewSession tables are untouched.
    """

    __tablename__ = "coach_sessions"

    id = Column(Integer, primary_key=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)

    title = Column(String(120), default="New chat")
    messages = Column(JSON, nullable=True)  # [{role: user|coach, content: str}]
    active_practice = Column(JSON, nullable=True)  # {question, category, difficulty, kind, last_feedback}

    # Coaching context remembered across messages
    target_role = Column(String(255), nullable=True)
    mode = Column(String(40), default="coaching")  # coaching | strict_interviewer
    tone = Column(String(40), default="friendly")  # friendly | strict | warm | neutral

    # Latest analysis snapshot loaded into coaching context (source_kind +
    # source_id: video interview analysis or live interview report).
    snapshot = Column(JSON, nullable=True)
    snapshot_source_kind = Column(String(30), nullable=True)  # video | live
    snapshot_source_id = Column(Integer, nullable=True)
