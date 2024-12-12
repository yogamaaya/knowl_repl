from langchain_huggingface import HuggingFaceEmbeddings
from langchain_core.documents.base import Document
from transformers import DistilBertTokenizerFast
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.chains import ConversationalRetrievalChain
from langchain_chroma import Chroma
from dotenv import load_dotenv
import os
from google.oauth2 import service_account
from googleapiclient.discovery import build
import json
from langchain.prompts import PromptTemplate

# import requests
# from bs4 import BeautifulSoup

# Load environment variables
load_dotenv()
google_api_key = os.getenv('GOOGLE_API_KEY')

chat_history = []
text = ''

SCOPES = ['https://www.googleapis.com/auth/drive.readonly']
creds = json.loads(os.environ['GOOGLE_CREDENTIALS'])


# Get contents in webpage from GDocs
def updateText():
    doc_id = "1noKTwTEgvl1G74vYutrdwBZ6dWMiNOuoZWjGR1mwC9A"
    try:
        credentials = service_account.Credentials.from_service_account_info(
            creds, scopes=SCOPES)
        service = build('docs', 'v1', credentials=credentials)
        document = service.documents().get(documentId=doc_id).execute()
        text = ''
        # Changed doc_content to document.get('body', {}).get('content', [])
        for element in document.get('body', {}).get('content', []):
            if 'paragraph' in element:
                for para_element in element['paragraph']['elements']:
                    if 'textRun' in para_element:
                        text += para_element['textRun']['content']

        return text
    except Exception as e:
        return str(e)


# Handle user query submission
def on_submit(query):
    global chat_history, text

    # Refresh and update the text from URL
    text = updateText()
    print("Updated text:", text[:100])

    # Create new tokenizer and text splitter using DistilBERT
    tokenizer = DistilBertTokenizerFast.from_pretrained(
        "distilbert-base-uncased")
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=512,
        chunk_overlap=20,
        length_function=lambda x: len(tokenizer.encode(x)))

    # Split text into chunks and create embeddings using a sentence transformer
    text_chunks = text_splitter.split_text(text)
    documents = [Document(page_content=chunk) for chunk in text_chunks]

    # Load model and create embeddings
    model_name = "paraphrase-MiniLM-L3-v2"
    model_kwargs = {'device': 'cpu'}
    encode_kwargs = {'normalize_embeddings': False}

    embedding_function = HuggingFaceEmbeddings(model_name=model_name,
                                               model_kwargs=model_kwargs,
                                               encode_kwargs=encode_kwargs)

    # Configure Gemini for fast, detailed responses
    llm = ChatGoogleGenerativeAI(
        model="gemini-pro",
        temperature=0.1,
        max_output_tokens=300,
        google_api_key=google_api_key,
    )

    # Create a new Chroma database and QA chain
    db = Chroma.from_documents(documents, embedding_function)

    # Optimize QA chain for speed and detail
    retriever = db.as_retriever(search_kwargs={"k": 2})
    prompt_template = PromptTemplate(
        input_variables=["question", "context"],
        template=
        """As a kind, friendly and empathetic assistant, acknowledge the thoughtfulness of the question. 
        Then provide a detailed response that:
        1. Starts with a simple kind acknowledgement.
        2. Stays strictly focused on the given context only.
        3. Uses specific examples and references from the text.
        4. Ends always with a concluding thank you.
        Question: {question}
        Context: {context}

        """)

    qa_chain = ConversationalRetrievalChain.from_llm(
        llm=llm,
        retriever=retriever,
        chain_type="stuff",
        return_source_documents=False,
        memory=None,
        combine_docs_chain_kwargs={'prompt': prompt_template})

    # Process the query
    result = qa_chain({"question": query, "chat_history": chat_history[-2:]})
    chat_history.append((query, result['answer']))
    return result["answer"]
