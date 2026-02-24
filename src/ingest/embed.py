"""Embedding and ChromaDB storage for document chunks."""

import torch
import chromadb
from sentence_transformers import SentenceTransformer

from config import (
    COLLECTION_NAME,
    EMBEDDING_DIM,
    EMBEDDING_MODEL,
    VECTOR_STORE_DIR,
)


def load_embedder() -> SentenceTransformer:
    """Load the embedding model."""
    return SentenceTransformer(EMBEDDING_MODEL)


def init_collection(reset: bool = True) -> tuple[chromadb.ClientAPI, chromadb.Collection]:
    """Initialize ChromaDB client and collection."""
    VECTOR_STORE_DIR.mkdir(parents=True, exist_ok=True)
    client = chromadb.PersistentClient(path=str(VECTOR_STORE_DIR))

    if reset:
        try:
            client.delete_collection(COLLECTION_NAME)
        except Exception:
            pass
        collection = client.create_collection(
            name=COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"},
        )
    else:
        collection = client.get_or_create_collection(
            name=COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"},
        )

    return client, collection


def get_collection() -> tuple[chromadb.ClientAPI, chromadb.Collection]:
    """Get existing ChromaDB collection (for querying)."""
    client = chromadb.PersistentClient(path=str(VECTOR_STORE_DIR))
    collection = client.get_collection(name=COLLECTION_NAME)
    return client, collection


def embed_and_store(
    embedder: SentenceTransformer,
    collection: chromadb.Collection,
    chunks: list[dict],
    metadata: dict,
) -> None:
    """Embed chunks and store in ChromaDB with metadata."""
    if not chunks:
        return

    ids = [c["chunk_id"] for c in chunks]
    # Prepend embeddinggemma document prompt for better retrieval
    paper_title = metadata.get("title", "none")
    documents = [c["text"] for c in chunks]
    prompted_docs = [f'title: {paper_title} | text: {doc}' for doc in documents]
    metadatas = []
    for c in chunks:
        m = {
            "source_id": c["source_id"],
            "section_title": c["section_title"],
            "filename": metadata.get("filename", ""),
            "title": metadata.get("title", ""),
            "year": metadata.get("year", 0),
            "type": metadata.get("type", ""),
            "authors": ", ".join(metadata.get("authors", [])),
        }
        metadatas.append(m)

    # Embed in small batches to manage MPS memory
    embeddings = embedder.encode(
        prompted_docs,
        show_progress_bar=False,
        batch_size=2,
    ).tolist()

    # Free MPS GPU memory after encoding
    if torch.backends.mps.is_available():
        torch.mps.empty_cache()

    # Truncate to configured dimensions if needed
    if len(embeddings[0]) > EMBEDDING_DIM:
        embeddings = [e[:EMBEDDING_DIM] for e in embeddings]

    collection.add(
        ids=ids,
        documents=documents,
        embeddings=embeddings,
        metadatas=metadatas,
    )
