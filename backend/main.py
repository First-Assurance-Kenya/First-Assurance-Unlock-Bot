from fastapi import FastAPI

from backend.routes.unlock import router as unlock_router


app = FastAPI(
    title="Account Unlock Automation System",
    description="API for automated Active Directory account unlocking",
    version="1.0.0"
)


app.include_router(unlock_router)


@app.get("/")
def root():
    return {
        "system": "Account Unlock Automation System",
        "status": "online"
    }