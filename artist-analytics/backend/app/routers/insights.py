from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import service
from ..db import get_db
from ..insights import claude
from ..models import Insight
from ..schemas import InsightOut, QuestionIn
from .artists import get_artist

router = APIRouter(prefix="/api/artists/{artist_id}/insights", tags=["insights"])


@router.get("", response_model=list[InsightOut])
def history(artist_id: int, limit: int = 20, db: Session = Depends(get_db)):
    return db.scalars(select(Insight).where(Insight.artist_id == artist_id).order_by(Insight.created_at.desc()).limit(limit)).all()


@router.post("/report", response_model=InsightOut)
def report(artist_id: int, db: Session = Depends(get_db)):
    a = get_artist(db, artist_id)
    facts, extras = service.facts(db, artist_id), service.extras(db, artist_id)
    text, model = claude.trend_report(a.name, facts, extras)
    ins = Insight(artist_id=artist_id, kind="report", context={"facts": facts, "extras": extras}, content=text, model=model)
    db.add(ins)
    db.commit()
    return ins


@router.post("/ask", response_model=InsightOut)
def ask(artist_id: int, body: QuestionIn, db: Session = Depends(get_db)):
    a = get_artist(db, artist_id)
    facts, extras = service.facts(db, artist_id), service.extras(db, artist_id)
    text, model = claude.answer(a.name, facts, extras, body.question)
    ins = Insight(artist_id=artist_id, kind="question", question=body.question, context={"facts": facts}, content=text, model=model)
    db.add(ins)
    db.commit()
    return ins
