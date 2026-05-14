from supabase import create_client, Client
from app.config import settings

if not settings.SUPABASE_URL:
    raise ValueError("SUPABASE_URL is missing from .env")

if not settings.SUPABASE_ANON_KEY:
    raise ValueError("SUPABASE_ANON_KEY is missing from .env")

supabase: Client = create_client(
    settings.SUPABASE_URL,
    settings.SUPABASE_ANON_KEY
)