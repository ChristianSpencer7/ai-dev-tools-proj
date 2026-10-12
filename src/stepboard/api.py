from fastapi import FastAPI

from stepboard.db import Database


def create_api(db: Database) -> FastAPI:
    """Public web endpoint. Phase 3 adds the Fitbit callback; phase 4 adds step pushes."""
    app = FastAPI(title="stepboard")

    @app.get("/health")
    def health() -> dict:
        return {"ok": True, "members": len(db.members())}

    return app
