from fastapi import APIRouter

from src.infra.storage import chat_history_store

router = APIRouter()


@router.get("/history/{session_id}")
def get_history(session_id: str):
    return {"history": chat_history_store.get_history(session_id)}


@router.delete("/history/{session_id}")
def clear_history(session_id: str):
    chat_history_store.clear_history(session_id)
    return {"status": "cleared"}

