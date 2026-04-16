from datetime import datetime, timedelta, time

SLOT_INTERVAL_MINUTES = 30


def generate_pickup_slots(opening_hour: int, closing_hour: int):
    now = datetime.now()
    today = now.date()

    if opening_hour is None or closing_hour is None:
        raise ValueError("Vendor timings not configured")
        
    opening_time = datetime.combine(today, time(opening_hour, 0))
    closing_time = datetime.combine(today, time(closing_hour, 0))

    if now >= closing_time:
        return []

    slots = []
    current = opening_time

    while current <= closing_time:
        if current > now:
            slots.append(current.strftime("%I:%M %p"))
        current += timedelta(minutes=SLOT_INTERVAL_MINUTES)

    return slots