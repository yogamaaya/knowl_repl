from langchain_huggingface import HuggingFaceEmbeddings
from langchain_core.documents.base import Document
from transformers import DistilBertTokenizerFast
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_openai import OpenAI
from langchain.chains import ConversationalRetrievalChain
from langchain_chroma import Chroma
from dotenv import load_dotenv
import os
import requests
from bs4 import BeautifulSoup

# Load environment variables
load_dotenv()
openai_api_key = os.getenv('OPENAI_API_KEY')

chat_history = []
text = ''


# Get contents in webpage from URL with requests and BeautifulSoup
def updateText():
    url = "https://textdoc.co/fCAmzT1RyWtlN9qj"
    response = requests.get(url)
    soup = BeautifulSoup(response.content, "html.parser")
    text = soup.get_text(strip=True)
    text = text.replace(
        "Online Text Editor - Create, Edit, Share and Save Text FilesTextdocZipdocWriteurlTxtshareOnline CalcLoading…Open FileSave to Drive",
        "")
    text = text.replace("/ Drive Add-on", "")
    return text


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
        chunk_overlap=24,
        length_function=lambda x: len(tokenizer.encode(x)))

    # Split text into chunks and create embeddings using a sentence transformer
    text_chunks = text_splitter.split_text(text)

    documents = [Document(page_content=chunk) for chunk in text_chunks]

    model_name = "paraphrase-MiniLM-L3-v2"
    model_kwargs = {'device': 'cpu'}
    encode_kwargs = {'normalize_embeddings': False}

    embedding_function = HuggingFaceEmbeddings(model_name=model_name,
                                               model_kwargs=model_kwargs,
                                               encode_kwargs=encode_kwargs)

    # Create a new Chroma database and QA chain
    db = Chroma.from_documents(documents, embedding_function)
    qa_chain = ConversationalRetrievalChain.from_llm(OpenAI(temperature=0.1),
                                                     db.as_retriever())

    # Process the query
    result = qa_chain({"question": query, "chat_history": chat_history})
    chat_history.append((query, result['answer']))
    return result["answer"]
