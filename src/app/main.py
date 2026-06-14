import uvicorn
from fastapi import FastAPI, APIRouter
from app.auth.controller import router as auth_router
from app.offers.controller import router as offers_router
from app.user.controller import router as user_router

app = FastAPI()

app.include_router(auth_router, prefix="/api/v2/auth")
app.include_router(offers_router, prefix="/api/v2/offers")
app.include_router(user_router, prefix="/api/v2/user")

if __name__ == "__main__":
    # Used for debugging purposes
    uvicorn.run(app, host="0.0.0.0", port=8000)