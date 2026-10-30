"""Deterministic mixed-language tokenization and corpus-local Okapi BM25.

No dictionary, provider, learned parameters, global cache or gold-answer input.
"""

from collections import Counter
from dataclasses import dataclass, field
import math
import re


PROTOCOL = "mixed-bm25-v2"
SOURCE_PROTOCOL = "mixed-bm25-source-v2"
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


@dataclass(slots=True)
class FieldTerms:
    length: int
    frequencies: Counter[str]
    matched_fields: list[str]


def summarize_fields(document: dict[str, str], requested: set[str]) -> FieldTerms:
    """Discard source text and vocabulary unrelated to this query."""
    counts: Counter[str] = Counter()
    length, matched = 0, []
    for key, value in document.items():
        tokens = tokenize(value)
        length += len(tokens)
        frequencies = Counter(term for term in tokens if term in requested)
        counts.update(frequencies)
        if frequencies:
            matched.append(key)
    return FieldTerms(length, counts, matched)


@dataclass
class CorpusStatistics:
    terms: list[str]
    document_count: int = 0
    total_length: int = 0
    document_frequency: Counter[str] = field(default_factory=Counter)

    def add(self, document: FieldTerms) -> None:
        # Unmatched and empty documents still belong to the corpus statistics.
        self.document_count += 1
        self.total_length += document.length
        self.document_frequency.update(document.frequencies.keys())

    def score(self, document: FieldTerms) -> float:
        if not document.frequencies:
            return 0.0
        average = self.total_length / self.document_count
        score = 0.0
        for term in self.terms:
            count = document.frequencies.get(term, 0)
            if count:
                frequency = self.document_frequency[term]
                inverse = math.log1p((self.document_count - frequency + .5) / (frequency + .5))
                score += inverse * count * (K1 + 1) / (count + K1 * (1 - B + B * document.length / average))
        return score


def rank_fields(documents: list[dict[str, str]], query: str) -> tuple[list[str], list[tuple[float, list[str]]]]:
    """Standard BM25 over concatenated fields, without custom field boosts."""
    terms = list(dict.fromkeys(tokenize(query)))
    corpus = CorpusStatistics(terms)
    summaries = [summarize_fields(document, set(terms)) for document in documents]
    for summary in summaries:
        corpus.add(summary)
    return terms, [(corpus.score(summary), summary.matched_fields) for summary in summaries]
