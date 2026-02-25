import os
import json
from langchain_core.documents import Document
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.vectorstores import FAISS

# Cached embeddings model
_embeddings = None

def get_embeddings():
    """Get or create the embeddings model (cached)."""
    global _embeddings
    if _embeddings is None:
        _embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
    return _embeddings

def build_vector_database(data_path: str = None, db_dir: str = None) -> int:
    """
    Build the FAISS vector database from chat JSON data.
    
    Args:
        data_path: Path to the JSON file with chat data
        db_dir: Directory to save the FAISS index
        
    Returns:
        Number of documents indexed
    """
    # Default paths
    if data_path is None:
        data_path = os.path.join("data", "discord_chat.json")
    if db_dir is None:
        db_dir = os.path.join("data", "faiss_db")
    
    # Load the chat data
    with open(data_path, "r", encoding="utf-8") as f:
        chats = json.load(f)

    # Convert to LangChain Documents with Metadata
    documents = []
    for chat in chats:
        doc = Document(
            page_content=chat["content"],
            metadata={
                "author": chat["author"],
                "timestamp": chat["timestamp"],
                "source": chat["source"]
            }
        )
        documents.append(doc)

    if not documents:
        raise ValueError("No documents found in the chat data")

    # Get embeddings model
    embeddings = get_embeddings()

    # Create the Vector Database
    vectorstore = FAISS.from_documents(
        documents=documents,
        embedding=embeddings
    )
    
    # Save the FAISS index to disk
    vectorstore.save_local(db_dir)
    
    return len(documents)

def main():
    """CLI entry point."""
    print("Loading chat data...")
    
    try:
        count = build_vector_database()
        print(f"Vector database built successfully with {count} documents!")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()