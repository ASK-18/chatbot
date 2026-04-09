import os
from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_chroma import Chroma

CHROMA_DIR = os.path.join(os.path.dirname(__file__), "chroma_db")


def get_retriever(pdf_path):
    """
    Loads the vector database if it exists,
    else builds embeddings from the PDF and stores them.
    """

    # Good embedding model for semantic search
    embeddings = HuggingFaceEmbeddings(
        model_name="sentence-transformers/all-MiniLM-L6-v2"
    )

    # If DB exists → load it (fast)
    if os.path.exists(CHROMA_DIR) and os.listdir(CHROMA_DIR):
        vectorstore = Chroma(
            persist_directory=CHROMA_DIR,
            embedding_function=embeddings
        )
        print("Loaded existing Chroma DB.")
    else:
        print("Building new Chroma DB from PDF...")

        # Load PDF
        loader = PyPDFLoader(pdf_path)
        pages = loader.load()

        # BETTER chunking for insurance docs
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=1500,     # bigger chunks for dense text
            chunk_overlap=200    # small overlap for context continuity
        )
        docs = splitter.split_documents(pages)

        # Create vector DB
        vectorstore = Chroma.from_documents(
            docs,
            embedding=embeddings,
            persist_directory=CHROMA_DIR
        )
        print("Chroma DB created and saved.")

    # Return retriever with improved search behavior
    return vectorstore.as_retriever(
        search_kwargs={"k": 3}  
    )