from fastapi import HTTPException

ALLOWED_TRANSITIONS = {
    "PLACED": ["PAID", "CANCELLED"],
    "PAID": ["PREPARING"],
    "PREPARING": ["DELIVERED"],
    "DELIVERED": [],
    "CANCELLED": []
}

#This function checks: “Is the order allowed to move from its current status to the new status?”
def validate_transition(current_status: str, new_status: str):
    if new_status not in ALLOWED_TRANSITIONS.get(current_status, []):
        raise HTTPException(
            status_code=400,
            detail=f"Invalid status transition from {current_status} to {new_status}"
        )