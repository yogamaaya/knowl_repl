
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
from datetime import datetime, timedelta
from langchain.prompts import PromptTemplate
from collections import OrderedDict
import time

load_dotenv()

class SessionManager:
    def __init__(self, max_sessions=1000, ttl_hours=24):
        self.qa_chains = OrderedDict()
        self.chat_histories = OrderedDict()
        self.embeddings_cache = OrderedDict()
        self.max_sessions = max_sessions
        self.ttl = ttl_hours * 3600
        
    def cleanup_old_sessions(self):
        current_time = time.time()
        for ip in list(self.qa_chains.keys()):
            if current_time - self.qa_chains[ip].get('timestamp', 0) > self.ttl:
                del self.qa_chains[ip]
                del self.chat_histories[ip]
                
    def add_session(self, ip_address):
        if len(self.qa_chains) >= self.max_sessions:
            self.qa_chains.popitem(last=False)
            self.chat_histories.popitem(last=False)
        self.qa_chains[ip_address] = {'chain': None, 'timestamp': time.time()}
        self.chat_histories[ip_address] = []
        
    def get_qa_chain(self, ip_address):
        if ip_address in self.qa_chains:
            self.qa_chains[ip_address]['timestamp'] = time.time()
            return self.qa_chains[ip_address]['chain']
        return None

    def update_qa_chain(self, ip_address, chain):
        if ip_address not in self.qa_chains:
            self.add_session(ip_address)
        self.qa_chains[ip_address]['chain'] = chain
        self.qa_chains[ip_address]['timestamp'] = time.time()

session_manager = SessionManager()
openai_api_key = os.getenv('OPENAI_API_KEY')
SCOPES = ['https://www.googleapis.com/auth/drive.readonly']
creds = json.loads(os.environ['GOOGLE_CREDENTIALS'])
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def create_embeddings(text, doc_id):
    if doc_id in session_manager.embeddings_cache:
        return session_manager.embeddings_cache[doc_id]
        
    tokenizer = DistilBertTokenizerFast.from_pretrained("distilbert-base-uncased")
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=512,
        chunk_overlap=20,
        length_function=lambda x: len(tokenizer.encode(x)))

    text_chunks = text_splitter.split_text(text)
    documents = [Document(page_content=chunk) for chunk in text_chunks]

    embedding_function = HuggingFaceEmbeddings(
        model_name="paraphrase-MiniLM-L3-v2",
        model_kwargs={'device': 'cpu'},
        encode_kwargs={'normalize_embeddings': False}
    )

    db = Chroma.from_documents(documents, embedding_function)
    
    if len(session_manager.embeddings_cache) > 10:
        session_manager.embeddings_cache.popitem(last=False)
    session_manager.embeddings_cache[doc_id] = db
    
    return db

def on_submit(query, ip_address):
    session_manager.cleanup_old_sessions()
    
    qa_chain = session_manager.get_qa_chain(ip_address)
    if not qa_chain:
        initialize_embeddings(ip_address)
        qa_chain = session_manager.get_qa_chain(ip_address)

    result = qa_chain({"question": query, "chat_history": session_manager.chat_histories[ip_address][-2:]})
    answer = result['answer']
    session_manager.chat_histories[ip_address].append((query, answer))

    # Text-to-speech processing
    credentials_dict = json.loads(os.environ['GOOGLE_CLOUD_CREDENTIALS'])
    client = texttospeech.TextToSpeechClient.from_service_account_info(credentials_dict)
    
    synthesis_input = texttospeech.SynthesisInput(text=answer)
    voice = texttospeech.VoiceSelectionParams(
        language_code="en-US",
        name="en-US-Studio-O",
        ssml_gender=texttospeech.SsmlVoiceGender.FEMALE
    )
    
    audio_config = texttospeech.AudioConfig(
        audio_encoding=texttospeech.AudioEncoding.MP3,
        speaking_rate=1.0,
        pitch=0.0
    )

    response = client.synthesize_speech(
        input=synthesis_input,
        voice=voice,

def initialize_embeddings(ip_address=None):
    logger.info("\n=== Initializing Default Embeddings ===")
    doc_id = "1noKTwTEgvl1G74vYutrdwBZ6dWMiNOuoZWjGR1mwC9A"
    logger.info(f"Using default doc_id: {doc_id}")
    
    text = get_text_from_doc(doc_id)
    logger.info(f"Retrieved text length: {len(text)}")
    
    db = create_embeddings(text, doc_id)
    
    qa_chain = ConversationalRetrievalChain.from_llm(
        OpenAI(temperature=0.7, 
              model_name="gpt-3.5-turbo", 
              openai_api_key=openai_api_key),
        db.as_retriever(),
        return_source_documents=True,
        verbose=True
    )
    
    if ip_address:
        session_manager.update_qa_chain(ip_address, qa_chain)
    
    return qa_chain

        audio_config=audio_config
    )

    audio_path = f"static/response_{ip_address}.mp3"
    with open(audio_path, "wb") as out:
        out.write(response.audio_content)

    return {"text": answer, "audio_url": f"/static/response_{ip_address}.mp3"}

# Other functions remain similar but use session_manager instead of globals
