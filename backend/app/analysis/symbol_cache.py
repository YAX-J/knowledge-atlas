"""Process-local LRU of immutable symbol metadata; never stores source text or access grants."""
from collections import OrderedDict
from dataclasses import dataclass
from threading import RLock

from app.analysis.parsers.java import JavaSymbol


@dataclass(frozen=True)
class SymbolSnapshot:
    symbols: tuple[JavaSymbol, ...]
    truncated: bool
    has_syntax_errors: bool = False


class SymbolCache:
    def __init__(self, max_entries=128, max_bytes=8 * 1024 * 1024):
        self.max_entries, self.max_bytes = max_entries, max_bytes
        self._entries = OrderedDict()
        self._lock = RLock()
        self.clear()

    def clear(self):
        with self._lock:
            self._entries.clear()
            self.bytes = self.hits = self.misses = 0

    def get_or_compute(self, key, compute):
        with self._lock:
            if key in self._entries:
                self.hits += 1
                self._entries.move_to_end(key)
                return self._entries[key][0]
            self.misses += 1
        # Parsers belong to an invocation, never a shared mutable cached parser.
        result = compute()
        weight = 1024 + sum(512 + sum(len(value.encode('utf-8')) for value in
            (item.kind, item.name, item.qualified_name, item.owner or '')) for item in result.symbols)
        with self._lock:
            if key in self._entries:
                return self._entries[key][0]
            if weight <= self.max_bytes and self.max_entries > 0:
                while self._entries and (len(self._entries) >= self.max_entries or self.bytes + weight > self.max_bytes):
                    _, (_, removed) = self._entries.popitem(last=False)
                    self.bytes -= removed
                self._entries[key] = result, weight
                self.bytes += weight
        return result

    def info(self):
        with self._lock:
            return dict(entries=len(self._entries), accounted_bytes=self.bytes, hits=self.hits, misses=self.misses)


symbol_cache = SymbolCache()
