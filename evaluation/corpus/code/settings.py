MAX_IMPORT_FILES = 50
MAX_GITHUB_BYTES = 20 * 1024 * 1024

def import_budget() -> tuple[int, int]:
    return MAX_IMPORT_FILES, MAX_GITHUB_BYTES
