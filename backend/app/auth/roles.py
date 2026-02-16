#role-based access guard
from fastapi import Depends, HTTPException, status
from app.auth.deps import get_current_user
from app import models

def require_role(*allowed_roles: str): # *allowed_roles: str allows for any number of roles to be passed in and it is stored as a tuple
    def role_checker(
        current_user: models.User = Depends(get_current_user)
    ):
        if current_user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to access this resource"
            )
        return current_user
    
    return role_checker