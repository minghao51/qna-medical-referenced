import hashlib
import json
import logging
import math
import os
import re
from pathlib import Path
from typing import List, Dict, Set

import google.genai as genai
from dotenv import load_dotenv
import nltk
from nltk.stem.snowball import SnowballStemmer
from nltk.corpus import stopwords

load_dotenv()

logger = logging.getLogger(__name__)

DATA_DIR = Path("data")
VECTOR_DIR = DATA_DIR / "vectors"
VECTOR_DIR.mkdir(exist_ok=True)

EMBEDDING_MODEL = "gemini-embedding-001"

try:
    ENGLISH_STOPWORDS = set(stopwords.words("english"))
except LookupError:
    nltk.download("stopwords", quiet=True)
    ENGLISH_STOPWORDS = set(stopwords.words("english"))

MEDICAL_STOPWORDS = {
    "patient", "patients", "year", "years", "month", "months",
    "old", "male", "female", "gender", "age", "case", "cases",
    "study", "group", "result", "results", "data", "analysis",
    "method", "methods", "background", "objective", "conclusion"
}
ALL_STOPWORDS = ENGLISH_STOPWORDS | MEDICAL_STOPWORDS

STEMMER = SnowballStemmer("english")


def _content_hash(content: str) -> str:
    return hashlib.sha256(content.encode()).hexdigest()[:16]


def _get_words(text: str) -> List[str]:
    words = re.findall(r'\b[\w-]+\b', text.lower())
    result = []
    i = 0
    while i < len(words):
        word = words[i]
        if i + 1 < len(words) and word.endswith('-'):
            word = word + words[i + 1]
            i += 1
        result.append(word)
        i += 1
    return result


def _should_stem(word: str) -> bool:
    if not word:
        return False
    if "-" in word:
        return False
    if word.isupper() and len(word) > 1:
        return False
    if len(word) <= 2:
        return False
    return True


def _preprocess_word(word: str) -> str:
    word = word.lower()
    if _should_stem(word):
        word = STEMMER.stem(word)
    return word


class VectorStore:
    def __init__(
        self,
        collection_name: str = "medical_docs",
        semantic_weight: float = 0.6,
        keyword_weight: float = 0.2,
        boost_weight: float = 0.2
    ):
        self.collection_name = collection_name
        self.semantic_weight = semantic_weight
        self.keyword_weight = keyword_weight
        self.boost_weight = boost_weight
        self.client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
        self.embeddings_file = VECTOR_DIR / f"{collection_name}.json"
        self.documents = self._load()
        self.content_hashes = set(self.documents.get("content_hashes", []))
        self.keyword_index = self._build_keyword_index()
        self._index_dirty = False
        self._doc_term_freqs = self._build_term_frequencies()

    def _load(self) -> dict:
        if self.embeddings_file.exists():
            with open(self.embeddings_file, 'r') as f:
                return json.load(f)
        return {"ids": [], "contents": [], "embeddings": [], "metadatas": [], "content_hashes": []}

    def _save(self):
        self.documents["content_hashes"] = list(self.content_hashes)
        with open(self.embeddings_file, 'w') as f:
            json.dump(self.documents, f)

    def _tokenize(self, text: str) -> List[str]:
        words = _get_words(text)
        filtered = []
        for w in words:
            if w in ALL_STOPWORDS:
                continue
            if w.replace("-", "").isalpha():
                filtered.append(w)
        stemmed = [_preprocess_word(w) for w in filtered]
        return stemmed

    def _build_term_frequencies(self) -> Dict[int, Dict[str, int]]:
        term_freqs = {}
        for idx, content in enumerate(self.documents.get("contents", [])):
            tokens = self._tokenize(content)
            tf = {}
            for token in tokens:
                tf[token] = tf.get(token, 0) + 1
            term_freqs[idx] = tf
        return term_freqs

    def _build_keyword_index(self) -> dict:
        index = {}
        for idx, content in enumerate(self.documents.get("contents", [])):
            tokens = self._tokenize(content)
            unique_tokens = set(tokens)
            for token in unique_tokens:
                if token not in index:
                    index[token] = []
                index[token].append(idx)
        return index

    def _rebuild_index_if_needed(self):
        if self._index_dirty:
            self.keyword_index = self._build_keyword_index()
            self._doc_term_freqs = self._build_term_frequencies()
            self._index_dirty = False

    def _keyword_score(self, query: str) -> dict:
        self._rebuild_index_if_needed()
        
        query_tokens = self._tokenize(query)
        if not query_tokens:
            return {}
        
        total_docs = len(self.documents.get("contents", []))
        if total_docs == 0:
            return {}
        
        scores = {}
        
        for token in set(query_tokens):
            if token not in self.keyword_index:
                continue
            
            doc_ids = self.keyword_index[token]
            idf = math.log((total_docs + 1) / (len(doc_ids) + 1)) + 1
            
            for doc_idx in doc_ids:
                tf = self._doc_term_freqs.get(doc_idx, {}).get(token, 0)
                tf_idf = (1 + math.log(tf)) * idf if tf > 0 else 0
                scores[doc_idx] = scores.get(doc_idx, 0) + tf_idf
        
        return scores

    def _embed(self, texts: List[str], batch_size: int = 10) -> List[List[float]]:
        all_embeddings = []
        for i in range(0, len(texts), batch_size):
            batch = texts[i:i+batch_size]
            result = self.client.models.embed_content(
                model=EMBEDDING_MODEL,
                contents=batch
            )
            all_embeddings.extend([e.values for e in result.embeddings])
        return all_embeddings

    def add_documents(self, documents: List[dict], batch_size: int = 10):
        texts = [doc["content"] for doc in documents]
        ids = [doc["id"] for doc in documents]
        metadatas = []
        for doc in documents:
            meta = {"source": doc["source"]}
            if "page" in doc:
                meta["page"] = doc["page"]
            metadatas.append(meta)

        embeddings = self._embed(texts, batch_size)

        for i, doc_id in enumerate(ids):
            content_hash = _content_hash(texts[i])
            if doc_id not in self.documents["ids"] and content_hash not in self.content_hashes:
                self.documents["ids"].append(doc_id)
                self.documents["contents"].append(texts[i])
                self.documents["embeddings"].append(embeddings[i])
                self.documents["metadatas"].append(metadatas[i])
                self.content_hashes.add(content_hash)

        self.documents["ids"] = list(self.documents["ids"])
        self.documents["contents"] = list(self.documents["contents"])
        self.documents["embeddings"] = list(self.documents["embeddings"])
        self.documents["metadatas"] = list(self.documents["metadatas"])

        self._save()
        self._index_dirty = True

    def similarity_search(self, query: str, top_k: int = 5, hybrid: bool = True) -> List[dict]:
        if not self.documents["contents"]:
            return []

        self._rebuild_index_if_needed()

        keyword_scores = self._keyword_score(query) if hybrid else {}

        try:
            query_embedding = self._embed([query])[0]
            use_semantic = True
        except Exception as e:
            logger.warning(f"Embedding failed, falling back to keyword-only search: {e}")
            use_semantic = False

        max_kw_score = max(keyword_scores.values()) if keyword_scores else 1

        source_boost = {"pdf": 1.0, "csv": 0.5}

        final_scores = []
        for i, emb in enumerate(self.documents["embeddings"]):
            if use_semantic:
                semantic_score = self._cosine_similarity(query_embedding, emb)
            else:
                semantic_score = 0.0

            source = self.documents["metadatas"][i].get("source", "")
            boost = source_boost.get("pdf", 1.0) if ".pdf" in source else source_boost.get("csv", 0.5)

            if hybrid and keyword_scores:
                kw_score = keyword_scores.get(i, 0) / max_kw_score if max_kw_score > 0 else 0
                if use_semantic:
                    combined = self.semantic_weight * semantic_score + self.keyword_weight * kw_score + self.boost_weight * boost
                else:
                    combined = (1 - self.boost_weight) * kw_score + self.boost_weight * boost
            else:
                combined = semantic_score * boost

            final_scores.append(combined)

        top_indices = sorted(range(len(final_scores)), key=lambda i: final_scores[i], reverse=True)[:top_k]

        results = []
        for idx in top_indices:
            results.append({
                "id": self.documents["ids"][idx],
                "content": self.documents["contents"][idx],
                "source": self.documents["metadatas"][idx].get("source", "unknown"),
                "page": self.documents["metadatas"][idx].get("page"),
                "score": final_scores[idx]
            })
        return results

    def _cosine_similarity(self, a: List[float], b: List[float]) -> float:
        dot_product = sum(x * y for x, y in zip(a, b))
        magnitude_a = sum(x * x for x in a) ** 0.5
        magnitude_b = sum(x * x for x in b) ** 0.5
        return dot_product / (magnitude_a * magnitude_b) if magnitude_a * magnitude_b > 0 else 0

    def clear(self):
        self.documents = {"ids": [], "contents": [], "embeddings": [], "metadatas": [], "content_hashes": []}
        self.content_hashes = set()
        self.keyword_index = {}
        self._doc_term_freqs = {}
        self._index_dirty = False
        if self.embeddings_file.exists():
            self.embeddings_file.unlink()


_vector_store = None


def get_vector_store() -> VectorStore:
    global _vector_store
    if _vector_store is None:
        _vector_store = VectorStore()
    return _vector_store
