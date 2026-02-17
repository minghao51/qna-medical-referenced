from pathlib import Path
from typing import List

from pypdf import PdfReader


class PDFLoader:
    def __init__(self, data_dir: str = "data/raw"):
        self.data_dir = Path(data_dir)

    def load_pdf(self, pdf_path: str) -> str:
        reader = PdfReader(pdf_path)
        text = ""
        for page in reader.pages:
            text += page.extract_text() + "\n"
        return text

    def load_all_pdfs(self) -> List[dict]:
        documents = []
        pdf_files = list(self.data_dir.glob("*.pdf"))

        for pdf_file in pdf_files:
            reader = PdfReader(str(pdf_file))
            pages = []
            for page_num, page in enumerate(reader.pages, 1):
                text = page.extract_text()
                if text:
                    pages.append({
                        "page": page_num,
                        "content": text
                    })

            documents.append({
                "id": pdf_file.stem,
                "source": str(pdf_file.name),
                "pages": pages
            })

        return documents


def get_documents() -> List[dict]:
    loader = PDFLoader()
    return loader.load_all_pdfs()
