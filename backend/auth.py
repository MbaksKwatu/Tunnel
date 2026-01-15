import os
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from supabase import create_client, Client

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

url = os.environ.get("SUPABASE_URL")
key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")  # Use service role key for admin operations
supabase: Client = create_client(url, key)

async def get_current_user(token: str = Depends(oauth2_scheme)):
    try:
        # Verify token with Supabase
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
