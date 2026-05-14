from dotenv import load_dotenv
from fastapi.openapi.utils import get_openapi
import os

load_dotenv()


class Settings:
    APP_NAME: str = os.getenv("APP_NAME", "Upwork Proposal AI")
    APP_VERSION: str = os.getenv("APP_VERSION", "0.1.0")
    DEBUG: bool = os.getenv("DEBUG", "False").lower() == "true"
    SUPABASE_URL: str = os.getenv("SUPABASE_URL", "")
    SUPABASE_ANON_KEY: str = os.getenv("SUPABASE_ANON_KEY", "")


settings = Settings()


def configure_openapi(app):
    """
    Adds BearerAuth security scheme to Swagger UI.
    Call this once in main.py after app is created.
    """

    def custom_openapi():
        if app.openapi_schema:
            return app.openapi_schema
        schema = get_openapi(
            title=settings.APP_NAME,
            version=settings.APP_VERSION,
            routes=app.routes,
        )
        schema.setdefault("components", {})["securitySchemes"] = {
            "BearerAuth": {
                "type": "http",
                "scheme": "bearer",
                "bearerFormat": "JWT",
            }
        }
        app.openapi_schema = schema
        return app.openapi_schema

    app.openapi = custom_openapi
