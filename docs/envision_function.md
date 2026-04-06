### 1. Hybrid/Semantic Entity Matching vs. HyDE
They are complementary but serve different purposes in the retrieval pipeline.

* **HyDE (Hypothetical Document Embeddings):** This is **Generative Expansion**. You ask the LLM to "hallucinate" a perfect answer, then embed *that* answer to find real documents. It helps when the query is a question but the documents are declarative (e.g., "What is HBP?" vs. "Hypertension is defined as...").
* **Semantic Entity Matching:** This is **Normalization/Grounding**. It ensures that "HBP," "High Blood Pressure," and "Hypertension" all map to the same unique concept ID (e.g., `UMLS:C0020538`).

#### Abstract Implementation

**A. HyDE (Generative Expansion)**
```python
def hyde_retrieval(query, model):
    # 1. Generate hypothetical clinical note/answer
    hypothetical_doc = model.generate(f"Write a brief medical explanation for: {query}")
    # 2. Embed the hallucination
    query_vec = embedding_model.encode(hypothetical_doc)
    # 3. Search vector DB
    return vector_db.search(query_vec)
```

**B. Semantic Entity Matching (Glossary/Taxonomy Mapping)**
This is where your `semantic_matcher` likely shines—resolving entities before the search starts.
```python
def normalized_search(query, matcher):
    # 1. Extract entities (NER)
    entities = ner_model.extract(query) # ['HBP']
    # 2. Resolve to standard taxonomy (using your semantic_matcher)
    normalized_terms = [matcher.resolve(e) for e in entities] # ['Hypertension']
    # 3. Augment query: "HBP Hypertension"
    augmented_query = f"{query} {' '.join(normalized_terms)}"
    return vector_db.search(embedding_model.encode(augmented_query))
```

---

### 2. Evaluation Rigor: Real-time vs. Batch
Running judges on golden datasets is the gold standard for **benchmarking** (offline), but for a medical system, you need a **Guardrail Judge** (online).

* **Offline (What you do now):** Essential for tuning your chunk size, embedding model, and top-k. It gives you your "System Accuracy."
* **Online (Every Query):** This is about **Faithfulness**. Even if your system is 95% accurate, you don't want the user to see the 5% where it hallucinates a dosage.

**Proposed Strategy:**
Use a "cheap" judge (e.g., a smaller model like your local `OpenCode` or a quantized `Llama-3-8B`) to run a binary **Groundedness Check** on every production response. If it fails, trigger a "Refusal" or "Re-try."



---

### 3. NIL Prediction: The "Hard Stop"
NIL (Not-In-Lexicon/No-Information-Found) prediction shouldn't rely solely on vector scores. Vector cosine similarity is notoriously "moody"—a score of 0.7 might be a perfect match in one index and total noise in another.

**The "Hard Stop" workflow:**
1.  **Candidate Filter (Vector Score):** If top-1 similarity is < 0.6 (example threshold), stop immediately.
2.  **Sufficiency Check (LLM-as-a-judge):** If the score passes, send the top-k chunks to a "NIL Evaluator" prompt:
    > "Given the provided context, can the question '{query}' be answered accurately? If no, respond with [NIL]."



Since you are already working on **novel class detection** in your `semantic_matcher` project, you can actually use it to flag when a query falls outside your ingested knowledge base's "taxonomy" entirely, effectively predicting NIL before you even touch the vector DB.
