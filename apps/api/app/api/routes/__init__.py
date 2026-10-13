from app.api.routes.arcs import router as arcs_router
from app.api.routes.chapters import router as chapters_router
from app.api.routes.characters import router as characters_router
from app.api.routes.health import router as health_router
from app.api.routes.memory import router as memory_router
from app.api.routes.plot import router as plot_router
from app.api.routes.research import router as research_router
from app.api.routes.projects import router as projects_router
from app.api.routes.settings import router as settings_router
from app.api.routes.story import router as story_router
from app.api.routes.world import router as world_router

__all__ = [
    "arcs_router",
    "chapters_router",
    "characters_router",
    "health_router",
    "memory_router",
    "plot_router",
    "research_router",
    "projects_router",
    "settings_router",
    "story_router",
    "world_router",
]
