from fastapi import HTTPException

ALLOWED_TRANSITIONS = {
    "PLACED": ["PAID", "CANCELLED"],
    "PAID": ["PREPARING", "CANCELLED"],
    "PREPARING": ["DELIVERED", "CANCELLED"],
    "DELIVERED": [],
    "CANCELLED": [],
}


def validate_transition(current_status: str, new_status: str):
    if new_status not in ALLOWED_TRANSITIONS.get(current_status, []):
        raise HTTPException(
            status_code=400,
            detail=f"Invalid status transition from {current_status} to {new_status}",
        )
