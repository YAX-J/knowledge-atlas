"""Deterministic mixed-language tokenization and corpus-local Okapi BM25.

No dictionary, provider, learned parameters, global cache or gold-answer input.
"""

from collections import Counter
import math
import re


PROTOCOL = "mixed-bm25-v1"
K1 = 1.2
B = .75
HAN = re.compile(r"([\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff\U00020000-\U0002ebef]+)")
WORD = re.compile(r"[^\W_]+(?:[_./:+#%\-][^\W_]+)*", re.UNICODE)


def tokenize(text: str) -> list[str]:
    """Keep identifiers and their parts; Han characters plus adjacent bigrams."""
    tokens = []
    for part in HAN.split(text.casefold()):
        if HAN.fullmatch(part):
            tokens.extend(part)
            tokens.extend(part[index:index + 2] for index in range(len(part) - 1))
        else:
            for match in WORD.finditer(part):
                word = match.group()
                tokens.append(word)
                pieces = re.split(r"[_./:+#%\-]", word)
                if len(pieces) > 1:
                    tokens.extend(piece for piece in pieces if piece)
    return tokens


def rank_fields(documents: list[dict[str, str]], query: str) -> tuple[list[str], list[tuple[float, list[str]]]]:
    """Standard BM25 over concatenated fields, without custom field boosts."""
    terms = list(dict.fromkeys(tokenize(query)))
    requested = set(terms)
    frequencies, lengths, matched_fields = [], [], []
    for document in documents:
        counts, length, matched = Counter(), 0, []
        for key, value in document.items():
            tokens = tokenize(value)
            length += len(tokens)  # All tokens still affect length normalization.
            field = Counter(term for term in tokens if term in requested)
            counts.update(field)
            if field:
                matched.append(key)
        frequencies.append(counts)
        lengths.append(length)
        matched_fields.append(matched)
    n = len(documents)
    average = sum(lengths) / n if n else 0
    document_frequency = {term: sum(term in document for document in frequencies) for term in terms}
    scores = []
    for document, matched, length in zip(frequencies, matched_fields, lengths, strict=True):
        score = 0.0
        for term in terms:
            count = document.get(term, 0)
            if count:
                inverse = math.log1p((n - document_frequency[term] + .5) / (document_frequency[term] + .5))
                score += inverse * count * (K1 + 1) / (count + K1 * (1 - B + B * length / average))
        scores.append((score, matched))
    return terms, scores
