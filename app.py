import warnings
warnings.filterwarnings("ignore", category=UserWarning, module="pydantic")
warnings.filterwarnings("ignore", category=UserWarning, module="langchain_core")

import os
import streamlit as st

# Page config
st.set_page_config(
    page_title="Project Assistant",
    page_icon="🔬",
    layout="centered"
)

st.title("🔬 Project Assistant")
st.caption("Ask questions about the YOLO-Seg lab equipment dataset project")

# Check if database exists
DB_PATH = os.path.join(os.path.dirname(__file__), 'data', 'faiss_db', 'index.faiss')
db_exists = os.path.exists(DB_PATH)

# Sidebar
with st.sidebar:
    st.header("🔄 Data Sync")
    
    if st.button("📥 Fetch Latest Discord Messages", use_container_width=True):
        with st.spinner("Fetching messages from Discord..."):
            try:
                from fetcher import fetch_and_save_discord_messages
                count = fetch_and_save_discord_messages()
                st.success(f"Fetched {count} messages from Discord!")
                
                # Rebuild vector database
                with st.spinner("Rebuilding vector database..."):
                    from processing import build_vector_database
                    doc_count = build_vector_database()
                    
                    st.success(f"Vector database rebuilt with {doc_count} documents!")
                    st.info("The assistant is now ready. Please refresh the page.")
                    st.rerun()
                    
            except Exception as e:
                st.error(f"Error: {e}")
    
    st.divider()
    
    st.header("About")
    st.markdown("""
    This assistant uses **RAG (Retrieval-Augmented Generation)** to answer questions about the project.
    
    It searches through project communications from Discord and other sources to find relevant context before generating answers.
    """)
    
    st.divider()
    
    if st.button("🗑️ Clear Chat History", use_container_width=True):
        st.session_state.messages = []
        st.rerun()

# Show setup message if database doesn't exist
if not db_exists:
    st.warning("⚠️ **First Time Setup Required**")
    st.info("""
    The vector database has not been initialized yet.
    
    👈 Click **"Fetch Latest Discord Messages"** in the sidebar to:
    1. Pull messages from your Discord channel
    2. Build the searchable knowledge base
    
    Once complete, you can start asking questions!
    """)
    st.stop()

# Import generation module only after confirming DB exists
from generation import ask_question, retrieve_context
from generation import llm as llm_module

# Initialize chat history
if "messages" not in st.session_state:
    st.session_state.messages = []

# Display chat history
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# Chat input
if user_input := st.chat_input("Ask a question about the project..."):
    # Add user message to history
    st.session_state.messages.append({"role": "user", "content": user_input})
    
    with st.chat_message("user"):
        st.markdown(user_input)
    
    # Generate response
    with st.chat_message("assistant"):
        with st.spinner("Searching project communications..."):
            # Retrieve context and get answer using the generation module
            docs, context_string = retrieve_context(user_input)
            answer = ask_question(user_input)
            
            st.markdown(answer)
            
            # Show retrieved context in expander
            with st.expander("📄 View Retrieved Context"):
                for i, doc in enumerate(docs, 1):
                    meta = doc.metadata
                    st.markdown(f"**{i}. [{meta.get('author', 'Unknown')}]** ({meta.get('timestamp', 'Unknown')[:10]})")
                    st.caption(doc.page_content)
                    st.divider()
    
    # Add assistant response to history
    st.session_state.messages.append({"role": "assistant", "content": answer})
