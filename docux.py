import os
import streamlit as st
from langchain.chains import create_retrieval_chain, create_history_aware_retriever
from langchain.chains.combine_documents import create_stuff_documents_chain

from langchain_community.vectorstores import Chroma
from langchain_community.chat_message_histories import ChatMessageHistory
from langchain_community.document_loaders import PyPDFLoader

from langchain_core.chat_history import BaseChatMessageHistory
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.runnables.history import RunnableWithMessageHistory

from langchain_text_splitters import RecursiveCharacterTextSplitter

from langchain_groq import ChatGroq
from langchain_huggingface import HuggingFaceEmbeddings
# from dotenv import load_dotenv

# Initialize embeddings
embeddings = HuggingFaceEmbeddings(
    model_name="sentence-transformers/all-MiniLM-L6-v2",
    model_kwargs={'device': 'cpu'},  # or 'cuda' if you have GPU
    encode_kwargs={'normalize_embeddings': False}
)

# Setting up streamlit
st.title("DocuX : Chat with your PDFs 📚",)
st.subheader("Chat with your PDF using Gemma2-9b-It model 😎")
st.markdown("###### 🧠 Upload PDF's and chat with their content – powered by LLMs, embeddings & Groq 🚀")

# Groq API
api_key = st.text_input("Enter your Groq API key: ", type='password')

# Checking if the api key is provided
if api_key:
    llm = ChatGroq(groq_api_key=api_key, model_name='Gemma2-9b-It')

    # Chat interface
    session_id = st.text_input("Session ID", value='default_session')  # Fixed typo

    # Managing chat history with the session state
    if 'store' not in st.session_state:
        st.session_state.store = {}  # Initializing store with all ai and human messages

    uploaded_files = st.file_uploader("Choose A PDF File", type='pdf', accept_multiple_files=True)

    # Processing files
    if uploaded_files:
        documents = []
        for uploaded_file in uploaded_files:
            temp_pdf = f"./temp_{uploaded_file.name}"  # Make temp file unique
            with open(temp_pdf, 'wb') as file:
                file.write(uploaded_file.getvalue())
            
            loader = PyPDFLoader(temp_pdf)
            docs = loader.load()
            documents.extend(docs)
            
            # # Clean up temp file
            if os.path.exists(temp_pdf):
                os.remove(temp_pdf)
        
        # Splitting and creating embeddings for the docs
        text_splitter = RecursiveCharacterTextSplitter(chunk_size=5000, chunk_overlap=500)
        splits = text_splitter.split_documents(documents)
        vectorstore = Chroma.from_documents(documents=splits, embedding=embeddings)
        retriever = vectorstore.as_retriever()

        # Contextual system prompt
        contextual_sys_prompt = (
            "Given the chat history and the latest user question "
            "which might reference context in the chat history, "
            "formulate a standalone question which can be understood "
            "without the chat history. Do Not answer the question, "
            "just reformulate it if needed and otherwise return it as is."
        )
        
        contextual_question_prompt = ChatPromptTemplate.from_messages(
            [
                ("system", contextual_sys_prompt),
                MessagesPlaceholder("chat_history"),
                ('human', "{input}")
            ]
        )

        history_aware_retriever = create_history_aware_retriever(llm, retriever, contextual_question_prompt)

        # Answer question prompt
        system_prompt = (
            "You are an assistant for question-answering tasks. "
            "Use the following pieces of retrieved context to answer "
            "the question. If you don't know the answer, say that you "
            "don't know. Use three sentences maximum and keep the "
            "answer concise."
            "\n\n"
            "{context}"    
        )
        
        question_prompt = ChatPromptTemplate.from_messages(
            [
                ('system', system_prompt),
                MessagesPlaceholder('chat_history'),
                ("human", "{input}")
            ]
        )

        qa_chain = create_stuff_documents_chain(llm, question_prompt)
        rag_chain = create_retrieval_chain(history_aware_retriever, qa_chain)

        def get_session_history(session_id: str) -> BaseChatMessageHistory:
            if session_id not in st.session_state.store:
                st.session_state.store[session_id] = ChatMessageHistory()
            return st.session_state.store[session_id]
        
        conversational_rag_chain = RunnableWithMessageHistory(
            rag_chain,
            get_session_history,
            input_messages_key="input",
            history_messages_key='chat_history',
            output_messages_key='answer'
        )

        user_input = st.text_input("Your question: ") 
        if user_input:
            session_history = get_session_history(session_id)

            response = conversational_rag_chain.invoke(
                {"input": user_input},
                config={
                    'configurable': {'session_id': session_id}
                }
            )

            st.write("Store contents:", st.session_state.store)
            st.success(f'Assistant: {response["answer"]}')  
            
            st.write('Chat History:', session_history.messages)

else:
    st.warning('Please enter the Groq API key.')