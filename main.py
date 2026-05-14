import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from app.config import settings, configure_openapi
from app.routes import router

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    docs_url="/docs",
    redoc_url="/redoc",
)

app.include_router(router)

configure_openapi(app)


@app.exception_handler(404)
def not_found_handler(request: Request, exc):
    return JSONResponse(
        status_code=404,
        content={
            "status": "error",
            "message": f"Route {request.url.path} does not exist.",
            "available_routes": "/docs",
        },
    )


if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.DEBUG,
    )
