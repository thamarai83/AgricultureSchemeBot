def split_documents(documents: list, chunk_size: int = 1000, chunk_overlap: int = 150) -> list:
    from langchain_text_splitters import RecursiveCharacterTextSplitter

    if chunk_size <= 0 or chunk_overlap < 0 or chunk_overlap >= chunk_size:
        raise ValueError("Chunk overlap must be non-negative and smaller than chunk size.")

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        add_start_index=True,
    )
    return splitter.split_documents(documents)
