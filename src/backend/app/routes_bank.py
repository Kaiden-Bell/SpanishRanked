"""Word bank: the words and phrases the learner has logged, with meanings, forms and conjugations."""

from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from .deps import CurrentUser, get_db, ready_user
from .lexicon import bank
from .lexicon.enrich import preview

router = APIRouter(prefix="/api", tags=["word-bank"])


class BankEntryPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    # Empty string clears the field.
    user_translation: Annotated[str, StringConstraints(strip_whitespace=True, max_length=200)] | None = None
    note: Annotated[str, StringConstraints(strip_whitespace=True, max_length=1000)] | None = None


class BankAddIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    # One word or phrase each, typed the way a study term is ("quieres", "te extraño - I miss you").
    terms: list[Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]] = Field(
        min_length=1, max_length=50)


@router.post("/bank", status_code=201)
def add_to_bank(body: BankAddIn, request: Request, user: CurrentUser = Depends(ready_user), conn=Depends(get_db)):
    """Add words and phrases straight to the bank, outside a study session. Meanings, examples and
    conjugations are filled in by the same background lookups as session terms. No XP."""
    added, skipped = [], []
    with conn:
        for text in dict.fromkeys(body.terms):
            result = bank.add_manual(conn, request.app.state.verbs, user.id, text)
            (skipped if "skipped" in result else added).append(result)
    if added:
        request.app.state.enricher.kick()
    return {"added": added, "skipped": skipped}


@router.delete("/bank/{entry_id}", status_code=204)
def remove_from_bank(entry_id: int, user: CurrentUser = Depends(ready_user), conn=Depends(get_db)):
    """Only hand-added entries; a word a study session logged belongs to that session's history."""
    try:
        removed = bank.remove_manual(conn, user.id, entry_id)
    except LookupError:
        raise HTTPException(404, "Word not found.")
    if not removed:
        raise HTTPException(409, "This word was logged in a study session, so it stays in your bank.")


@router.get("/bank")
def list_bank(
    request: Request,
    q: str = Query("", max_length=100),
    kind: Literal["WORD", "PHRASE"] | None = None,
    sort: Literal["recent", "alpha", "weak"] = "recent",
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    user: CurrentUser = Depends(ready_user),
    conn=Depends(get_db),
):
    total, items = bank.list_entries(conn, user.id, q, kind, sort, limit, offset, verbs=request.app.state.verbs)
    return {"total": total, "items": items, "counts": bank.counts(conn, user.id)}


@router.get("/bank/{entry_id}")
def get_bank_entry(entry_id: int, request: Request, user: CurrentUser = Depends(ready_user), conn=Depends(get_db)):
    out = bank.detail(conn, request.app.state.verbs, user.id, entry_id)
    if out is None:
        raise HTTPException(404, "Word not found.")
    if out["lookup_status"] in ("pending", "unavailable"):
        request.app.state.enricher.kick()
    return out


@router.patch("/bank/{entry_id}")
def patch_bank_entry(
    entry_id: int, body: BankEntryPatch, request: Request, user: CurrentUser = Depends(ready_user), conn=Depends(get_db)
):
    if bank.get_entry_row(conn, user.id, entry_id) is None:
        raise HTTPException(404, "Word not found.")
    fields = body.model_dump(exclude_unset=True)
    with conn:
        for column, value in fields.items():
            conn.execute(f"UPDATE bank_entries SET {column} = ? WHERE id = ?", (value or None, entry_id))
    return bank.detail(conn, request.app.state.verbs, user.id, entry_id)


@router.get("/lookup")
def lookup(
    request: Request,
    term: str = Query(min_length=1, max_length=100),
    user: CurrentUser = Depends(ready_user),
    conn=Depends(get_db),
):
    state = request.app.state
    return preview(conn, state.sources, state.verbs, term)
