
from AskMeApp.chromaDb.document_ingestion import DocumentIngestion


from pathlib import Path
from statistics import mean




PDF_PATH = r"C:\Users\keith.chambers\Documents\Lab Results of Record march 26.pdf"

ingestion = DocumentIngestion(
    chroma_client=None,
    chunk_size=900,
    overlap=120
)

# Extract the PDF.
pages = ingestion.extract_pdf_text(PDF_PATH)

all_chunks = []

print("\nPDF CHUNKING TEST")
print("=" * 60)

for page_data in pages:

    page_number = page_data["page"]
    page_text = page_data["text"]

    chunks = ingestion.chunk_text(page_text)

    all_chunks.extend(chunks)

    print(f"\nPAGE {page_number}")
    print("-" * 60)
    print(f"Extracted characters: {len(page_text)}")
    print(f"Chunks generated: {len(chunks)}")

    for index, chunk in enumerate(chunks):

        print(f"\nCHUNK {index + 1}")
        print(f"Characters: {len(chunk)}")
        print(f"START: {chunk[:150]}")
        print(f"END:   {chunk[-150:]}")

        assert len(chunk) <= 900, (
            f"Chunk exceeds maximum size on page {page_number}"
        )

# Overall statistics.
sizes = [len(chunk) for chunk in all_chunks]

print("\n\nOVERALL RESULTS")
print("=" * 60)
print(f"Pages extracted: {len(pages)}")
print(f"Total characters: {sum(len(p['text']) for p in pages)}")
print(f"Total chunks: {len(all_chunks)}")
print(f"Minimum chunk size: {min(sizes)}")
print(f"Maximum chunk size: {max(sizes)}")
print(f"Average chunk size: {mean(sizes):.1f}")

print("\nAll chunk-size tests passed.")
