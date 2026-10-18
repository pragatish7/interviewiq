from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import os

DATABASE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))), "data")
os.makedirs(DATABASE_DIR, exist_ok=True)

DATABASE_URL = f"sqlite:///{os.path.join(DATABASE_DIR, 'interviewiq.db')}"

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def init_db():
    from app.models.models import Base as ModelBase
    ModelBase.metadata.create_all(bind=engine)
    _migrate()
    _migrate_coach_sessions()


def _migrate():
    """Add columns introduced after the initial schema was created."""
    import sqlite3
    db_path = os.path.join(DATABASE_DIR, 'interviewiq.db')
    if not os.path.exists(db_path):
        return
    conn = sqlite3.connect(db_path)
    try:
        cols = {row[1] for row in conn.execute("PRAGMA table_info(interviews)")}
        additions = {
            "interview_type": "VARCHAR(50) DEFAULT 'General'",
            "target_role": "VARCHAR(255)",
            "experience_level": "VARCHAR(50)",
            "job_description": "TEXT",
        }
        for name, ddl in additions.items():
            if name not in cols:
                conn.execute(f"ALTER TABLE interviews ADD COLUMN {name} {ddl}")
        conn.commit()
    finally:
        conn.close()


def _migrate_coach_sessions():
    """Ensure the AI Coach table exists on databases created before the
    feature shipped (create_all already handles brand-new databases)."""
    import sqlite3
    db_path = os.path.join(DATABASE_DIR, 'interviewiq.db')
    if not os.path.exists(db_path):
        return
    conn = sqlite3.connect(db_path)
    try:
        conn.execute(
            "CREATE TABLE IF NOT EXISTS coach_sessions ("
            "id INTEGER PRIMARY KEY,"
            "created_at DATETIME,"
            "updated_at DATETIME,"
            "title VARCHAR(120) DEFAULT 'New chat',"
            "messages JSON,"
            "active_practice JSON,"
            "target_role VARCHAR(255),"
            "mode VARCHAR(40) DEFAULT 'coaching',"
            "tone VARCHAR(40) DEFAULT 'friendly',"
            "snapshot JSON,"
            "snapshot_source_kind VARCHAR(30),"
            "snapshot_source_id INTEGER"
            ")"
        )
        conn.commit()
    finally:
        conn.close()
