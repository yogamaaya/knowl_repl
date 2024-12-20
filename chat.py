
import logging
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_core.documents.base import Document
from transformers import DistilBertTokenizerFast
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_openai import OpenAI
from langchain.chains import ConversationalRetrievalChain
from langchain_chroma import Chroma
from dotenv import load_dotenv
import os
from google.oauth2 import service_account
from googleapiclient.discovery import build
import json
from datetime import datetime
from langchain.prompts import PromptTemplate

load_dotenv()
openai_api_key = os.getenv('OPENAI_API_KEY')

# Store sessions and documents by IP address
qa_chains = {}
chat_histories = {}
doc_ids = {}  # Track document ID per IP
SCOPES = ['https://www.googleapis.com/auth/drive.readonly']
creds = json.loads(os.environ['GOOGLE_CREDENTIALS'])
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def create_doc():
    try:
        credentials = service_account.Credentials.from_service_account_info(
            creds, scopes=SCOPES)
        service = build('docs', 'v1', credentials=credentials)
        doc = service.documents().create(body={}).execute()
        return doc.get('documentId')
    except Exception as e:
        logger.error(f"Error creating document: {str(e)}")
        return None

def get_doc_title(doc_id):
    try:
        credentials = service_account.Credentials.from_service_account_info(
            creds, scopes=SCOPES)
        service = build('docs', 'v1', credentials=credentials)
        document = service.documents().get(documentId=doc_id).execute()
        return document.get('title', 'Untitled Document')
    except Exception as e:
        logger.error(f"Error getting document title: {str(e)}")
        return "Untitled Document"

def get_text_from_doc(doc_id):
    try:
        logger.info(f"Getting text from doc_id: {doc_id}")
        credentials = service_account.Credentials.from_service_account_info(
            creds, scopes=SCOPES)
        service = build('docs', 'v1', credentials=credentials)
        document = service.documents().get(documentId=doc_id).execute()
        textLst = []
        for element in document.get('body', {}).get('content', []):
            if 'paragraph' in element:
                line_content = ''
                for para_element in element['paragraph']['elements']:
                    if 'textRun' in para_element:
                        line_content += para_element['textRun']['content']
                if line_content.strip():
                    textLst.append(line_content)
        return '\n'.join(textLst)
    except Exception as e:
        logger.error(f"Error getting text: {str(e)}")
        return None

def create_embeddings(text, ip_address):
    if not text.strip():
        return False
        
    try:
        tokenizer = DistilBertTokenizerFast.from_pretrained("distilbert-base-uncased")
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=512,
            chunk_overlap=20,
            length_function=lambda x: len(tokenizer.encode(x)))

        text_chunks = text_splitter.split_text(text)
        documents = [Document(page_content=chunk) for chunk in text_chunks]

        model_name = "paraphrase-MiniLM-L3-v2"
        model_kwargs = {'device': 'cpu'}
        encode_kwargs = {'normalize_embeddings': False}

        embedding_function = HuggingFaceEmbeddings(
            model_name=model_name,
            model_kwargs=model_kwargs,
            encode_kwargs=encode_kwargs)

        llm = OpenAI(
            temperature=0.2,
            max_tokens=1500,
            model="gpt-3.5-turbo-instruct",
            presence_penalty=0.1,
        )

        db = Chroma.from_documents(documents, embedding_function)
        retriever = db.as_retriever(search_kwargs={"k": 2})

        qa_chains[ip_address] = ConversationalRetrievalChain.from_llm(
            llm=llm,
            retriever=retriever,
            chain_type="stuff",
            return_source_documents=False,
            memory=None)
            
        return True
    except Exception as e:
        logger.error(f"Error creating embeddings: {str(e)}")
        return False

def initialize_embeddings(ip_address):
    if ip_address not in doc_ids:
        try:
            # For new IP sessions, use last successful document from history
            with open('doc_history.txt', 'r') as f:
                doc_history = json.load(f)
                if doc_history:
                    doc_ids[ip_address] = doc_history[-1]['id']
                else:
                    doc_ids[ip_address] = "1noKTwTEgvl1G74vYutrdwBZ6dWMiNOuoZWjGR1mwC9A"  # Default
        except:
            doc_ids[ip_address] = "1noKTwTEgvl1G74vYutrdwBZ6dWMiNOuoZWjGR1mwC9A"  # Default
    
    text = get_text_from_doc(doc_ids[ip_address])
    if text:
        success = create_embeddings(text, ip_address)
        if success:
            return {"success": True, "doc_id": doc_ids[ip_address], "title": get_doc_title(doc_ids[ip_address])}
    
    return {"success": False}

def on_submit(query, ip_address):
    if ip_address not in qa_chains:
        initialize_embeddings(ip_address)
        
    if qa_chains[ip_address] is None:
        return {"text": "Error: No document loaded", "audio_url": None}
        
    chat_history = chat_histories.get(ip_address, [])
    result = qa_chains[ip_address]({"question": query, "chat_history": chat_history[-2:] if chat_history else []})
    answer = result['answer']
    chat_histories[ip_address] = chat_history + [(query, answer)]

    # Text-to-speech conversion (unchanged)
    from google.cloud import texttospeech
    credentials_dict = json.loads(os.environ['GOOGLE_CLOUD_CREDENTIALS'])
    client = texttospeech.TextToSpeechClient.from_service_account_info(credentials_dict)
    synthesis_input = texttospeech.SynthesisInput(text=answer)
    voice = texttospeech.VoiceSelectionParams(
        language_code="en-US",
        name="en-US-Studio-O",
        ssml_gender=texttospeech.SsmlVoiceGender.FEMALE)
    audio_config = texttospeech.AudioConfig(
        audio_encoding=texttospeech.AudioEncoding.MP3,
        speaking_rate=1.0,
        pitch=0.0)
    response = client.synthesize_speech(
        input=synthesis_input,
        voice=voice,
        audio_config=audio_config)
    
    audio_path = "static/response.mp3"
    with open(audio_path, "wb") as out:
        out.write(response.audio_content)

    return {"text": answer, "audio_url": "/static/response.mp3"}

def update_doc_for_ip(ip_address, new_doc_id):
    text = get_text_from_doc(new_doc_id)
    if text and create_embeddings(text, ip_address):
        doc_ids[ip_address] = new_doc_id
        chat_histories[ip_address] = []
        return True
    return False
