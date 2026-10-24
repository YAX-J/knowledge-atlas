package eval;

public final class EvidenceGuard {
    public static boolean isExactQuote(String chunk, String quote) {
        return chunk.contains(quote);
    }
}
