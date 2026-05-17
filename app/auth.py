from app.database import supabase


def signup_user(email: str, password: str):
    response = supabase.auth.sign_up(
        {
            "email": email,
            "password": password,
            "options": {
                "email_redirect_to": "http://localhost:8000/auth/confirm?confirmed=true"
            },
        }
    )
    return response


def login_user(email: str, password: str):
    response = supabase.auth.sign_in_with_password(
        {"email": email, "password": password}
    )
    return response


def get_current_user(token: str) -> dict:
    """
    Extracts user from JWT token.
    Returns user dict with id and email.
    """
    response = supabase.auth.get_user(token)
    if not response or not response.user:
        raise ValueError("Invalid or expired token.")
    return {
        "user_id": response.user.id,
        "email": response.user.email,
    }
