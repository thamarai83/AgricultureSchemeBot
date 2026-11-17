from pathlib import Path

from services.storage import DATA_DIR


FAISS_INDEX_DIR = DATA_DIR / "faiss_index"


def has_persisted_index() -> bool:
    index_file = FAISS_INDEX_DIR / "index.faiss"
    metadata_file = FAISS_INDEX_DIR / "index.pkl"
    if index_file.exists() != metadata_file.exists():
        raise RuntimeError("FAISS index files are incomplete; restore or remove the index.")
    return index_file.exists()


def load_vector_store(embeddings):
    if not has_persisted_index():
        return None

    from langchain_community.vectorstores import FAISS

    return FAISS.load_local(
        str(FAISS_INDEX_DIR),
        embeddings,
        allow_dangerous_deserialization=True,
    )


def add_documents_to_store(documents: list, embeddings, vector_store=None):
    from langchain_community.vectorstores import FAISS

    store = vector_store or load_vector_store(embeddings)
    if store is None:
        store = FAISS.from_documents(documents, embeddings)
    else:
        store.add_documents(documents)

    FAISS_INDEX_DIR.mkdir(parents=True, exist_ok=True)
    store.save_local(str(FAISS_INDEX_DIR))
    return store
