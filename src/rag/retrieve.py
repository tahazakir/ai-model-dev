"""Retrieval with metadata filtering and source diversification."""

from sentence_transformers import SentenceTransformer

from config import EMBEDDING_DIM, MAX_PER_SOURCE, TOP_K


def retrieve(
    collection,
    embedder: SentenceTransformer,
    query: str,
    top_k: int = TOP_K,
    year: int | None = None,
    author: str | None = None,
    doc_type: str | None = None,
) -> list[dict]:
    """
    Retrieve top-k chunks from ChromaDB with optional metadata filters.
    Returns list of dicts with keys: chunk_id, source_id, title, text, distance, section_title.
    """
    # Build where clause for metadata filtering
    where_conditions = []
    if year is not None:
        where_conditions.append({"year": {"$eq": year}})
    if author is not None:
        all_meta = collection.get(include=["metadatas"])
        matching_sources = list({
            m["source_id"]
            for m in all_meta["metadatas"]
            if author.lower() in m.get("authors", "").lower()
        })
        if matching_sources:
            where_conditions.append({"source_id": {"$in": matching_sources}})
        else:
            return []
    if doc_type is not None:
        where_conditions.append({"type": {"$eq": doc_type}})

    where = None
    if len(where_conditions) == 1:
        where = where_conditions[0]
    elif len(where_conditions) > 1:
        where = {"$and": where_conditions}

    # Embed query with embeddinggemma retrieval prompt
    prompted_query = f"task: search result | query: {query}"
    query_embedding = embedder.encode(prompted_query).tolist()
    if len(query_embedding) > EMBEDDING_DIM:
        query_embedding = query_embedding[:EMBEDDING_DIM]

    # Query ChromaDB
    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=top_k,
        where=where,
        include=["documents", "metadatas", "distances"],
    )

    # Parse results
    chunks = []
    if results["ids"] and results["ids"][0]:
        for i, chunk_id in enumerate(results["ids"][0]):
            meta = results["metadatas"][0][i]
            chunks.append({
                "chunk_id": chunk_id,
                "source_id": meta.get("source_id", ""),
                "title": meta.get("title", ""),
                "section_title": meta.get("section_title", ""),
                "text": results["documents"][0][i],
                "distance": results["distances"][0][i],
            })

    return chunks


def retrieve_diversified(
    collection,
    embedder: SentenceTransformer,
    query: str,
    top_k: int = TOP_K,
    max_per_source: int = MAX_PER_SOURCE,
    year: int | None = None,
    author: str | None = None,
    doc_type: str | None = None,
) -> list[dict]:
    """
    Retrieve with source diversity: fetch more than needed, then cap per source.
    This ensures synthesis queries get evidence from multiple papers.
    """
    raw_chunks = retrieve(
        collection, embedder, query,
        top_k=top_k * 2,
        year=year, author=author, doc_type=doc_type,
    )

    seen: dict[str, int] = {}
    diversified = []
    for chunk in raw_chunks:
        sid = chunk["source_id"]
        seen.setdefault(sid, 0)
        if seen[sid] < max_per_source:
            diversified.append(chunk)
            seen[sid] += 1
        if len(diversified) >= top_k:
            break

    return diversified
