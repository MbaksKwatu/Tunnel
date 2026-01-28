import os
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from supabase import create_client, Client
from typing import Optional

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

# Lazy Supabase client creation - only create when needed
_supabase_client: Optional[Client] = None

def get_supabase_client() -> Client:
    """Get or create Supabase client. Raises if env vars are missing."""
    global _supabase_client
    if _supabase_client is None:
        url = os.environ.get("SUPABASE_URL")
        key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
        if not url or not key:
            raise ValueError("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set")
        _supabase_client = create_client(url, key)
    return _supabase_client

async def get_current_user(token: str = Depends(oauth2_scheme)):
    try:
        # Verify token with Supabase
        supabase = get_supabase_client()
        user = supabase.auth.get_user(token)
        if not user or hasattr(user, 'error') and user.error:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication credentials",
                headers={"WWW-Authenticate": "Bearer"},
            )
        return user.user
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Could not validate credentials: {str(e)}",
            headers={"WWW-Authenticate": "Bearer"},
        )
