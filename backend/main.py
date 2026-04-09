import os
from fastapi import FastAPI
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
from huggingface_hub import InferenceClient
from rag_engine import get_retriever
from dotenv import load_dotenv

load_dotenv()

HF_TOKEN = os.getenv("HF_TOKEN")
PDF_PATH = os.path.join(os.path.dirname(__file__), "data", "insurance.pdf")

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Load retriever at startup
retriever = get_retriever(PDF_PATH)

# HuggingFace client
client = InferenceClient(token=HF_TOKEN)


class ChatRequest(BaseModel):
    message: str


def format_docs(docs):
    return "\n\n".join(doc.page_content for doc in docs) if docs else ""


@app.post("/chat")
def chat(req: ChatRequest):
    query = req.message.strip()

    try:
        # 1. Retrieve relevant context
        docs = retriever.invoke(query)
        context = format_docs(docs)

        if not context:
            return {
                "answer": (
                    "I couldn’t find relevant information in the document. "
                    "Please ask something related to insurance coverage, claims, policies, or benefits."
                )
            }

        # 2. System prompt
        system_prompt = (
            "You are an insurance assistant.\n"
            "Answer the user's question using ONLY the provided context.\n"
            "Explain the answer clearly and simply.\n"
            "Do NOT copy text word-for-word.\n"
            "If the question involves coverage or claims, add a short disclaimer.\n\n"
            f"Context:\n{context}"
        )

        # 3. LLM call
        response = client.chat_completion(
            model="meta-llama/Meta-Llama-3-8B-Instruct",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": query},
            ],
            max_tokens=200,
            temperature=0.1,
        )

        answer = response.choices[0].message.content.strip()

        # Optional safety disclaimer
        if any(word in query.lower() for word in ["coverage", "claim", "insured"]):
            answer += (
                "\n\nNote: This information is subject to policy terms and conditions. "
                "Please refer to your official policy document for exact details."
            )

        return {"answer": answer}

    except Exception as e:
        print(f"Error: {e}")
        return {
            "answer": (
                "I'm currently unable to process your request. "
                "Please try again later or ask a different insurance-related question."
            )
        }
