LEASE_SECONDS = 120
MAX_ATTEMPTS = 3

def can_retry(attempt_count: int) -> bool:
    return attempt_count < MAX_ATTEMPTS
