import os
from typing import List

from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_chroma import Chroma

from sentence_transformers import CrossEncoder
from langchain_core.documents import Document



# -----------------------------------------------------
# Configuration
# -----------------------------------------------------
BASE_DIR = os.path.dirname(__file__)
CHROMA_DIR = os.path.join(BASE_DIR, "chroma_db")

EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
RERANKER_MODEL = "cross-encoder/ms-marco-MiniLM-L-6-v2"

CHUNK_SIZE = 500
CHUNK_OVERLAP = 100

RETRIEVAL_K = 5     # first-stage retrieval
RERANK_TOP_K = 3     # final chunks sent to LLM


# -----------------------------------------------------
# Models
# -----------------------------------------------------
embeddings = HuggingFaceEmbeddings(model_name=EMBEDDING_MODEL)
reranker = CrossEncoder(RERANKER_MODEL)


# -----------------------------------------------------
# Vector Store
# -----------------------------------------------------
def load_vectorstore(pdf_path: str) -> Chroma:
    if os.path.exists(CHROMA_DIR) and os.listdir(CHROMA_DIR):
        print("✅ Loaded existing Chroma DB")
        return Chroma(
            persist_directory=CHROMA_DIR,
            embedding_function=embeddings
        )

    print("⚙️ Building Chroma DB from PDF...")

    loader = PyPDFLoader(pdf_path)
    pages = loader.load()

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
        separators=["\n\n", "\n", ".", " "]
    )

    docs = splitter.split_documents(pages)

    vectorstore = Chroma.from_documents(
        documents=docs,
        embedding=embeddings,
        persist_directory=CHROMA_DIR
    )

    print(f"✅ Indexed {len(docs)} chunks")
    return vectorstore


# -----------------------------------------------------
# RAG Retrieval + Rerank Pipeline
# -----------------------------------------------------
def retrieve_and_rerank(
    query: str,
    vectorstore: Chroma
) -> List[Document]:
    """
    1. Retrieve top‑K documents using embeddings
    2. Rerank using cross‑encoder
    3. Return best documents
    """

    retriever = vectorstore.as_retriever(
        search_kwargs={"k": RETRIEVAL_K}
    )

    docs = retriever.invoke(query)

    if not docs:
        return []

    # Prepare query-document pairs
    pairs = [(query, doc.page_content) for doc in docs]

    # Cross‑encoder scoring
    scores = reranker.predict(pairs)

    # Sort by score (descending)
    ranked_docs = sorted(
        zip(docs, scores),
        key=lambda x: x[1],
        reverse=True
    )

    return [doc for doc, _ in ranked_docs[:RERANK_TOP_K]]


# -----------------------------------------------------
# Public API
# -----------------------------------------------------
def get_rag_pipeline(pdf_path: str):
    vectorstore = load_vectorstore(pdf_path)

    def pipeline(query: str):
        return retrieve_and_rerank(query, vectorstore)

    return pipeline
def retrieve_and_rerank(query: str, vectorstore):
    retriever = vectorstore.as_retriever(
        search_kwargs={"k": RETRIEVAL_K}
    )

    retrieved_docs = retriever.invoke(query)

    print("\n🔍 RETRIEVED DOCUMENTS (Before Reranking):")
    for i, doc in enumerate(retrieved_docs, start=1):
        print(f"\n[{i}] Page: {doc.metadata.get('page')}")
        print(doc.page_content[:300])

    if not retrieved_docs:
        return []

    pairs = [(query, doc.page_content) for doc in retrieved_docs]
    scores = reranker.predict(pairs)

    ranked = sorted(
        zip(retrieved_docs, scores),
        key=lambda x: x[1],
        reverse=True
    )

    print("\n🏆 RERANKED DOCUMENTS (After Cross‑Encoder):")
    for i, (doc, score) in enumerate(ranked, start=1):
        print(
            f"\nRank {i} | Score: {score:.4f} | Page: {doc.metadata.get('page')}"
        )
        print(doc.page_content[:300])

    top_docs = [doc for doc, _ in ranked[:RERANK_TOP_K]]

    print("\n✅ FINAL DOCUMENTS SENT TO LLM:")
    for doc in top_docs:
        print(
            f"Page {doc.metadata.get('page')} → "
            f"{doc.page_content[:200]}"
        )

    return top_docs
