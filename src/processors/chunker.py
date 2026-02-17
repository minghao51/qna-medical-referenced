from typing import List


class TextChunker:
    def __init__(self, chunk_size: int = 800, chunk_overlap: int = 150):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

    def chunk_text(self, text: str, source: str = "unknown", doc_id: str = "doc", page: int = 1) -> List[dict]:
        chunks = []
        start = 0
        text_length = len(text)

        while start < text_length:
            end = start + self.chunk_size

            if end < text_length:
                for sep in ['\n\n', '\n', '. ']:
                    last_sep = text.rfind(sep, start, end)
                    if last_sep > start:
                        end = last_sep + len(sep)
                        break

            chunk_text = text[start:end].strip()
            if chunk_text:
                chunks.append({
                    "id": f"{doc_id}_chunk_{len(chunks)}",
                    "source": source,
                    "page": page,
                    "content": chunk_text
                })

            start = end - self.chunk_overlap if end < text_length else text_length

        return chunks

    def chunk_documents(self, documents: List[dict]) -> List[dict]:
        all_chunks = []
        for doc in documents:
            source = doc.get("source", "unknown")
            doc_id = doc.get("id", "doc")

            if "pages" in doc:
                for page_data in doc["pages"]:
                    page_num = page_data.get("page", 1)
                    text = page_data.get("content", "")
                    if text:
                        chunks = self.chunk_text(text, source, doc_id, page_num)
                        all_chunks.extend(chunks)
            else:
                chunks = self.chunk_text(
                    doc.get("content", ""),
                    source,
                    doc_id
                )
                all_chunks.extend(chunks)

        return all_chunks


def chunk_documents(documents: List[dict]) -> List[dict]:
    chunker = TextChunker()
    return chunker.chunk_documents(documents)
