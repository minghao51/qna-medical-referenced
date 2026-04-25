from src.app.routes.chat import router as chat_router
from src.app.routes.config import router as config_router
from src.app.routes.documents import router as documents_router
from src.app.routes.evaluation import router as evaluation_router
from src.app.routes.experiments import router as experiments_router
from src.app.routes.health import router as health_router
from src.app.routes.history import router as history_router

__all__ = [
    "chat_router",
    "config_router",
    "documents_router",
    "evaluation_router",
    "experiments_router",
    "health_router",
    "history_router",
]
