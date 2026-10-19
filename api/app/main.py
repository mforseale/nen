from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.database import Base, engine
from app.routers import auth, calendars, community, feed, pacts, users, workspace

app = FastAPI(
    title="Pact API",
    version="0.1.0",
    description="Backend for pact management and collaboration.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_origin_regex=r"https?://(localhost|127\.0\.0\.1)(:\d+)?",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

Base.metadata.create_all(bind=engine)

app.include_router(users.router, prefix="/api/v1")
app.include_router(pacts.router, prefix="/api/v1")
app.include_router(auth.router, prefix="/api/v1")
app.include_router(workspace.router, prefix="/api/v1")
app.include_router(calendars.router, prefix="/api/v1")
app.include_router(community.router, prefix="/api/v1")
app.include_router(feed.router, prefix="/api/v1")


@app.get("/api/v1/health")
def health_check():
    return {"status": "ok"}
