"""Shared pure identity normalization for request and persistence boundaries."""
import unicodedata


def normalize_name(value: str) -> str:
    return ' '.join(unicodedata.normalize('NFKC', value).casefold().split())
