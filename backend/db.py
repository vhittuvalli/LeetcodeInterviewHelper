"""Everything database-related lives here -- every other module (
leetcode_service, diagnosis, submission_history, spaced_repetition) calls
into the functions at the bottom of this file instead of touching
SQLAlchemy directly. That's a deliberate choice: it means each of those
modules can stay exactly as readable as it was when it was reading/writing
JSON files, and if the storage layer ever changes again, this is the only
file that has to.

Tables here mirror backend/db/schema.sql exactly -- that SQL is what
actually creates them in Supabase; these are just Python's view of
already-existing tables (create_all() is never called against a real
database, only against the in-memory SQLite used in tests).
"""
import os
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone

from sqlalchemy import (
    BigInteger,
    Column,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Text,
    UniqueConstraint,
    Uuid,
    create_engine,
)
from sqlalchemy.orm import declarative_base, sessionmaker

Base = declarative_base()

# Postgres's `bigint generated always as identity` (from schema.sql) handles
# auto-incrementing IDs regardless of column type. SQLite -- used only by
# the tests below, since this sandbox can't reach a real Postgres server --
# only auto-increments a primary key typed exactly as INTEGER, not BIGINT.
# with_variant() lets production keep real BigInteger while tests get a
# type SQLite knows how to auto-increment, without duplicating any models.
_id_type = BigInteger().with_variant(Integer(), "sqlite")


class User(Base):
    __tablename__ = "users"
    id = Column(Uuid, primary_key=True, default=uuid.uuid4)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class LeetCodeCredential(Base):
    __tablename__ = "leetcode_credentials"
    user_id = Column(Uuid, ForeignKey("users.id"), primary_key=True)
    cookie = Column(Text, nullable=False)
    csrf = Column(Text, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class ProblemDiagnosis(Base):
    __tablename__ = "problem_diagnoses"
    id = Column(_id_type, primary_key=True, autoincrement=True)
    user_id = Column(Uuid, ForeignKey("users.id"), nullable=False)
    title_slug = Column(Text, nullable=False)
    status = Column(Text, nullable=False)  # 'pending' | 'optimal'
    last_submission_id = Column(BigInteger)
    last_verdict = Column(Text)
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    __table_args__ = (UniqueConstraint("user_id", "title_slug"),)


class DiagnosisHistory(Base):
    __tablename__ = "diagnosis_history"
    id = Column(_id_type, primary_key=True, autoincrement=True)
    user_id = Column(Uuid, ForeignKey("users.id"), nullable=False)
    title_slug = Column(Text, nullable=False)
    verdict = Column(Text, nullable=False)
    result = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class SubmissionCache(Base):
    __tablename__ = "submission_cache"
    user_id = Column(Uuid, ForeignKey("users.id"), primary_key=True)
    title_slug = Column(Text, primary_key=True)
    submission_id = Column(BigInteger, nullable=False)
    status = Column(Text, nullable=False)
    lang = Column(Text, nullable=False)
    submitted_at = Column(DateTime(timezone=True), nullable=False)
    code = Column(Text, nullable=False)
    fetched_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class SpacedRepetitionQueue(Base):
    __tablename__ = "spaced_repetition_queue"
    id = Column(_id_type, primary_key=True, autoincrement=True)
    user_id = Column(Uuid, ForeignKey("users.id"), nullable=False)
    title_slug = Column(Text, nullable=False)
    assigned_date = Column(Date, nullable=False)
    reviewed_at = Column(DateTime(timezone=True))


# ---------------------------------------------------------------------------
# Connection setup -- lazy, same reasoning as llm_client.py's _get_client():
# importing this module shouldn't require DATABASE_URL to already be set,
# only actually touching the database should.
# ---------------------------------------------------------------------------

_engine = None
_SessionLocal = None


def _get_engine():
    global _engine
    if _engine is None:
        url = os.environ.get("DATABASE_URL", "")
        if not url:
            raise RuntimeError(
                "DATABASE_URL is not set -- add it to backend/.env (the connection "
                "string from Supabase's Project Settings -> Database -> Connection string)."
            )
        _engine = create_engine(url, pool_pre_ping=True)
    return _engine


def _get_session_factory():
    global _SessionLocal
    if _SessionLocal is None:
        _SessionLocal = sessionmaker(bind=_get_engine())
    return _SessionLocal


def use_engine(engine):
    """Test-only hook: point this module at an already-created engine (e.g.
    an in-memory SQLite one) instead of building a Postgres one from
    DATABASE_URL. Also resets the cached default-user id, since tests run
    against a fresh, empty database each time."""
    global _engine, _SessionLocal, _default_user_id_cache
    _engine = engine
    _SessionLocal = sessionmaker(bind=_engine)
    _default_user_id_cache = None


@contextmanager
def session_scope():
    """A session that commits on success, rolls back on error, and always
    closes -- every function below uses this via `with` instead of
    duplicating try/commit/except/rollback/finally six times over."""
    session = _get_session_factory()()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


# ---------------------------------------------------------------------------
# Default user (Phase 1: single-user). Every other function below takes a
# user_id -- for now, everything in app.py passes get_default_user_id().
# When real multi-user auth exists, only this one function's caller needs
# to change (to "the currently authenticated user"), not every query.
# ---------------------------------------------------------------------------

_default_user_id_cache = None


def get_default_user_id():
    global _default_user_id_cache
    if _default_user_id_cache is not None:
        return _default_user_id_cache

    with session_scope() as session:
        user = session.query(User).first()
        if user is None:
            user = User(id=uuid.uuid4())
            session.add(user)
            session.flush()  # so user.id is populated before we read it below
        _default_user_id_cache = user.id

    return _default_user_id_cache


# ---------------------------------------------------------------------------
# Credentials (replaces leetcode_service.py's _COOKIE / _CSRF globals)
# ---------------------------------------------------------------------------

def get_credentials(user_id):
    """Returns (cookie, csrf) or (None, None) if nothing's been synced yet."""
    with session_scope() as session:
        row = session.query(LeetCodeCredential).filter_by(user_id=user_id).first()
        if row is None:
            return None, None
        return row.cookie, row.csrf


def upsert_credentials(user_id, cookie, csrf):
    with session_scope() as session:
        row = session.query(LeetCodeCredential).filter_by(user_id=user_id).first()
        if row is None:
            session.add(LeetCodeCredential(user_id=user_id, cookie=cookie, csrf=csrf))
        else:
            row.cookie = cookie
            row.csrf = csrf
            row.updated_at = datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# Diagnosis state (replaces diagnosis_state.json)
# ---------------------------------------------------------------------------

def get_diagnosed_slugs(user_id):
    """titleSlugs with status='optimal' -- what select_problems_to_diagnose()
    excludes from future batches."""
    with session_scope() as session:
        rows = session.query(ProblemDiagnosis.title_slug).filter_by(user_id=user_id, status="optimal").all()
        return {r[0] for r in rows}


def get_pending_diagnosis(user_id, title_slug):
    """Returns {'submissionId':..., 'verdict':...} for a still-unresolved
    problem, or None if it's never been diagnosed or is already optimal."""
    with session_scope() as session:
        row = (
            session.query(ProblemDiagnosis)
            .filter_by(user_id=user_id, title_slug=title_slug, status="pending")
            .first()
        )
        if row is None:
            return None
        return {"submissionId": row.last_submission_id, "verdict": row.last_verdict}


def record_diagnosis(user_id, title_slug, submission_id, verdict, result=None):
    status = "optimal" if verdict == "OPTIMAL" else "pending"

    with session_scope() as session:
        row = session.query(ProblemDiagnosis).filter_by(user_id=user_id, title_slug=title_slug).first()
        if row is None:
            session.add(ProblemDiagnosis(
                user_id=user_id,
                title_slug=title_slug,
                status=status,
                last_submission_id=submission_id,
                last_verdict=verdict,
            ))
        else:
            row.status = status
            row.last_submission_id = submission_id
            row.last_verdict = verdict
            row.updated_at = datetime.now(timezone.utc)

        if result is not None:
            session.add(DiagnosisHistory(
                user_id=user_id, title_slug=title_slug, verdict=verdict, result=result,
            ))


# ---------------------------------------------------------------------------
# Submission cache (replaces submission_history.json)
# ---------------------------------------------------------------------------

def get_cached_submission(user_id, title_slug):
    with session_scope() as session:
        row = session.query(SubmissionCache).filter_by(user_id=user_id, title_slug=title_slug).first()
        if row is None:
            return None

        # Values are always stored in UTC (see upsert_cached_submission), but
        # not every driver hands them back tz-aware -- SQLite in particular
        # always returns naive datetimes regardless of what was stored,
        # which would silently shift .timestamp() by the server's local
        # offset if not corrected here. Postgres returns proper tz-aware
        # values, so this is a no-op there.
        submitted_at = row.submitted_at
        if submitted_at.tzinfo is None:
            submitted_at = submitted_at.replace(tzinfo=timezone.utc)

        return {
            "id": row.submission_id,
            "status": row.status,
            "lang": row.lang,
            "timestamp": int(submitted_at.timestamp()),
            "code": row.code,
        }


def upsert_cached_submission(user_id, title_slug, submission):
    """submission: {'id', 'status', 'lang', 'timestamp' (unix int), 'code'}"""
    submitted_at = datetime.fromtimestamp(submission["timestamp"], tz=timezone.utc)

    with session_scope() as session:
        row = session.query(SubmissionCache).filter_by(user_id=user_id, title_slug=title_slug).first()
        if row is None:
            session.add(SubmissionCache(
                user_id=user_id,
                title_slug=title_slug,
                submission_id=submission["id"],
                status=submission["status"],
                lang=submission["lang"],
                submitted_at=submitted_at,
                code=submission["code"],
            ))
        else:
            row.submission_id = submission["id"]
            row.status = submission["status"]
            row.lang = submission["lang"]
            row.submitted_at = submitted_at
            row.code = submission["code"]
            row.fetched_at = datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# Spaced repetition queue (replaces spaced_repetition_state.json)
# ---------------------------------------------------------------------------

def get_reviewed_slugs(user_id):
    """Every titleSlug ever marked reviewed, regardless of when."""
    with session_scope() as session:
        rows = (
            session.query(SpacedRepetitionQueue.title_slug)
            .filter(SpacedRepetitionQueue.user_id == user_id, SpacedRepetitionQueue.reviewed_at.isnot(None))
            .distinct()
            .all()
        )
        return {r[0] for r in rows}


def get_current_pick(user_id, today):
    """The most recent not-yet-reviewed assignment for today, or None."""
    with session_scope() as session:
        row = (
            session.query(SpacedRepetitionQueue)
            .filter_by(user_id=user_id, assigned_date=today)
            .filter(SpacedRepetitionQueue.reviewed_at.is_(None))
            .order_by(SpacedRepetitionQueue.id.desc())
            .first()
        )
        if row is None:
            return None
        return {"titleSlug": row.title_slug}


def assign_problem(user_id, title_slug, today):
    with session_scope() as session:
        session.add(SpacedRepetitionQueue(user_id=user_id, title_slug=title_slug, assigned_date=today))


def mark_reviewed(user_id, title_slug, today):
    """Marks today's unreviewed assignment for title_slug as reviewed (if
    any). Takes title_slug explicitly (rather than just grabbing "whatever's
    pending today") so this can't accidentally mark the wrong problem
    reviewed if the caller and the DB's notion of "current" ever disagree --
    matches the old JSON version's mark_reviewed(slug), which always acted
    on the exact slug it was given."""
    with session_scope() as session:
        row = (
            session.query(SpacedRepetitionQueue)
            .filter_by(user_id=user_id, title_slug=title_slug, assigned_date=today)
            .filter(SpacedRepetitionQueue.reviewed_at.is_(None))
            .order_by(SpacedRepetitionQueue.id.desc())
            .first()
        )
        if row is not None:
            row.reviewed_at = datetime.now(timezone.utc)