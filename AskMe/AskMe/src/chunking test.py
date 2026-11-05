
from AskMeApp.chromaDb.document_ingestion import DocumentIngestion

# We only need to test chunking, so no Chroma client is required.
ingestion = DocumentIngestion(
    chroma_client=None,
    chunk_size=900,
    overlap=120
)

sample_text = """
Introduction

This is the first paragraph. It contains information
about the application and its architecture.

This is the second paragraph. It explains how the
document ingestion process works.

""" + ("This is a deliberately long sentence used to test " * 100)

chunks = ingestion.chunk_text(sample_text)

for index, chunk in enumerate(chunks):

    print(f"\nCHUNK {index + 1}")
    print(f"Characters: {len(chunk)}")
    print(chunk[:200])

    assert len(chunk) <= 900
