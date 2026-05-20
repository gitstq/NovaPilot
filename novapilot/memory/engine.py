"""Memory engine with TF-IDF semantic search for NovaPilot.

Implements TF-IDF keyword extraction, cosine similarity-based
semantic search, and memory classification using pure Python.
"""

import math
import re
from collections import Counter, defaultdict
from novapilot.memory.store import MemoryStore


# Stop words for text processing (common words to filter out)
STOP_WORDS = {
    "a", "an", "the", "is", "are", "was", "were", "be", "been", "being",
    "have", "has", "had", "do", "does", "did", "will", "would", "could",
    "should", "may", "might", "must", "shall", "can", "need", "dare",
    "ought", "used", "to", "of", "in", "for", "on", "with", "at", "by",
    "from", "as", "into", "through", "during", "before", "after", "above",
    "below", "between", "out", "off", "over", "under", "again", "further",
    "then", "once", "here", "there", "when", "where", "why", "how", "all",
    "both", "each", "few", "more", "most", "other", "some", "such", "no",
    "nor", "not", "only", "own", "same", "so", "than", "too", "very",
    "just", "because", "but", "and", "or", "if", "while", "that", "this",
    "these", "those", "it", "its", "i", "me", "my", "we", "our", "you",
    "your", "he", "him", "his", "she", "her", "they", "them", "their",
    "what", "which", "who", "whom", "about", "up", "down",
    "的", "了", "在", "是", "我", "有", "和", "就", "不", "人", "都",
    "一", "一个", "上", "也", "很", "到", "说", "要", "去", "你", "会",
    "着", "没有", "看", "好", "自己", "这",
}


class MemoryEngine:
    """Memory engine with TF-IDF semantic search.

    Provides intelligent memory storage and retrieval using
    TF-IDF (Term Frequency-Inverse Document Frequency) for
    keyword extraction and cosine similarity for semantic matching.
    """

    def __init__(self, store=None):
        """Initialize MemoryEngine.

        Args:
            store: Optional MemoryStore instance. Creates new one if None.
        """
        self.store = store or MemoryStore()
        self._idf_cache = {}
        self._doc_count = 0

    def _tokenize(self, text):
        """Tokenize text into words, filtering stop words.

        Handles both English and CJK text.

        Args:
            text: Input text string.

        Returns:
            List of lowercase word tokens.
        """
        # Extract words (including CJK characters)
        tokens = re.findall(
            r'[a-zA-Z0-9]+|[\u4e00-\u9fff]',
            text.lower()
        )

        # For CJK text, also extract bigrams
        cjk_chars = re.findall(r'[\u4e00-\u9fff]', text)
        if len(cjk_chars) >= 2:
            for i in range(len(cjk_chars) - 1):
                bigram = cjk_chars[i] + cjk_chars[i + 1]
                tokens.append(bigram)

        # Filter stop words and single characters
        filtered = [
            t for t in tokens
            if t not in STOP_WORDS and len(t) > 1
        ]

        return filtered

    def _compute_tf(self, tokens):
        """Compute term frequency for a list of tokens.

        TF(t) = (number of times t appears) / (total number of tokens)

        Args:
            tokens: List of word tokens.

        Returns:
            Dict mapping terms to their TF values.
        """
        if not tokens:
            return {}

        counter = Counter(tokens)
        total = len(tokens)
        return {term: count / total for term, count in counter.items()}

    def _compute_idf(self, term):
        """Compute inverse document frequency for a term.

        IDF(t) = log((1 + N) / (1 + df(t))) + 1
        where N = total documents, df(t) = documents containing term t.

        Args:
            term: Term string.

        Returns:
            IDF value (float).
        """
        if term in self._idf_cache:
            return self._idf_cache[term]

        # Count documents containing the term
        df = 0
        for entry in self.store._data.get("entries", []):
            if term in entry.get("content", "").lower():
                df += 1

        n = max(self.store.count(), 1)
        idf = math.log((1 + n) / (1 + df)) + 1
        self._idf_cache[term] = idf
        return idf

    def _compute_tfidf(self, tokens):
        """Compute TF-IDF vector for a list of tokens.

        Args:
            tokens: List of word tokens.

        Returns:
            Dict mapping terms to their TF-IDF values.
        """
        tf = self._compute_tf(tokens)
        tfidf = {}
        for term, tf_val in tf.items():
            idf = self._compute_idf(term)
            tfidf[term] = tf_val * idf
        return tfidf

    def _cosine_similarity(self, vec_a, vec_b):
        """Compute cosine similarity between two vectors.

        Args:
            vec_a: Dict mapping terms to values (sparse vector).
            vec_b: Dict mapping terms to values (sparse vector).

        Returns:
            Cosine similarity score (float between 0 and 1).
        """
        if not vec_a or not vec_b:
            return 0.0

        # Dot product (only common terms)
        common_terms = set(vec_a.keys()) & set(vec_b.keys())
        dot_product = sum(vec_a[t] * vec_b[t] for t in common_terms)

        # Magnitudes
        mag_a = math.sqrt(sum(v ** 2 for v in vec_a.values()))
        mag_b = math.sqrt(sum(v ** 2 for v in vec_b.values()))

        if mag_a == 0 or mag_b == 0:
            return 0.0

        return dot_product / (mag_a * mag_b)

    def remember(self, content, category="general", tags=None,
                 metadata=None):
        """Store a new memory with automatic keyword extraction.

        Args:
            content: Memory content string.
            category: Memory category ('conversation', 'knowledge', 'task', 'general').
            tags: Optional list of tag strings.
            metadata: Optional dict of additional metadata.

        Returns:
            Entry ID string.
        """
        # Auto-classify if category is 'general'
        if category == "general":
            category = self._classify_content(content)

        # Auto-extract tags from content
        auto_tags = self._extract_keywords(content, top_n=5)
        if tags:
            if isinstance(tags, str):
                tags = [tags]
            auto_tags = list(set(auto_tags + list(tags)))

        entry_id = self.store.add(
            content=content,
            category=category,
            tags=auto_tags,
            metadata=metadata,
        )

        # Invalidate IDF cache since document count changed
        self._idf_cache.clear()

        return entry_id

    def _classify_content(self, content):
        """Classify content into a memory category.

        Uses simple keyword matching to determine the best category.
        Task patterns are checked first since they are more specific.

        Args:
            content: Content string.

        Returns:
            Category string ('conversation', 'knowledge', 'task', 'general').
        """
        content_lower = content.lower()

        # Task indicators (checked first - more specific)
        task_patterns = [
            r'\b(todo|task|deadline|remind|schedule|finish|complete)\b',
            r'\b(need to|must|should|have to|plan to|buy|send|call|meet)\b',
            r'\bremember to\b',
        ]
        for pattern in task_patterns:
            if re.search(pattern, content_lower):
                return "task"

        # Knowledge indicators (checked after tasks)
        knowledge_patterns = [
            r'\b(fact|definition|formula|rule|law|theorem)\b',
            r'\b(memorize|note that|important)\b',
            r'\b(because|therefore|thus|hence|consequently)\b',
            r'\b(speed|distance|mass|energy)\b.*\b(is|are|equals)\b',
        ]
        for pattern in knowledge_patterns:
            if re.search(pattern, content_lower):
                return "knowledge"

        # Conversation indicators (default)
        return "conversation"

    def _extract_keywords(self, text, top_n=5):
        """Extract top keywords from text using TF-IDF.

        Args:
            text: Input text string.
            top_n: Number of top keywords to extract.

        Returns:
            List of keyword strings.
        """
        tokens = self._tokenize(text)
        if not tokens:
            return []

        tfidf = self._compute_tfidf(tokens)

        # Sort by TF-IDF score descending
        sorted_terms = sorted(tfidf.items(), key=lambda x: x[1], reverse=True)

        return [term for term, score in sorted_terms[:top_n]]

    def recall(self, query, top_k=5, category=None):
        """Search memories using TF-IDF semantic similarity.

        Args:
            query: Search query string.
            top_k: Number of top results to return.
            category: Optional category filter.

        Returns:
            List of dicts with 'entry', 'score', and 'keywords' keys.
        """
        query_tokens = self._tokenize(query)
        query_tfidf = self._compute_tfidf(query_tokens)

        if not query_tfidf:
            return []

        # Get candidate entries
        entries = self.store.list_all(category=category, limit=1000)

        # Score each entry
        scored = []
        for entry in entries:
            entry_tokens = self._tokenize(entry.get("content", ""))
            entry_tfidf = self._compute_tfidf(entry_tokens)

            similarity = self._cosine_similarity(query_tfidf, entry_tfidf)

            # Boost score for matching tags
            query_tags = set(query_tokens)
            entry_tags = set(entry.get("tags", []))
            tag_overlap = len(query_tags & entry_tags)
            boost = tag_overlap * 0.1

            total_score = similarity + boost

            if total_score > 0.01:  # Minimum threshold
                scored.append({
                    "entry": entry,
                    "score": round(total_score, 4),
                    "keywords": self._extract_keywords(
                        entry.get("content", ""), top_n=3
                    ),
                })

        # Sort by score descending
        scored.sort(key=lambda x: x["score"], reverse=True)
        return scored[:top_k]

    def forget(self, entry_id):
        """Delete a memory entry.

        Args:
            entry_id: Entry identifier.

        Returns:
            True if deleted, False if not found.
        """
        result = self.store.delete(entry_id)
        if result:
            self._idf_cache.clear()
        return result

    def list_memories(self, category=None, limit=20):
        """List memory entries.

        Args:
            category: Optional category filter.
            limit: Maximum entries to return.

        Returns:
            List of entry dicts.
        """
        return self.store.list_all(category=category, limit=limit)

    def search(self, query, limit=10):
        """Simple text search through memories.

        Args:
            query: Search query string.
            limit: Maximum results.

        Returns:
            List of matching entry dicts with scores.
        """
        return self.store.search(query, limit=limit)

    def get_stats(self):
        """Get memory engine statistics.

        Returns:
            Dict with memory statistics.
        """
        store_stats = self.store.get_stats()
        store_stats["idf_cache_size"] = len(self._idf_cache)
        return store_stats

    def clear(self, category=None):
        """Clear memories.

        Args:
            category: If specified, only clear this category.

        Returns:
            Number of entries deleted.
        """
        count = self.store.clear(category=category)
        if count > 0:
            self._idf_cache.clear()
        return count

    def export_memories(self, format_type="json"):
        """Export all memories.

        Args:
            format_type: Export format ('json' or 'jsonl').

        Returns:
            Exported data string.
        """
        return self.store.export_data(format_type=format_type)
