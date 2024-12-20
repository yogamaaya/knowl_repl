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

# Store sessions by IP address
qa_chains = {}
chat_histories = {}
text = ''
doc_id = ''
SCOPES = ['https://www.googleapis.com/auth/drive.readonly']
creds = json.loads(os.environ['GOOGLE_CREDENTIALS'])
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def create_doc(title=None):
    print("\n=== Creating New Document ===")
    global doc_id, text, qa_chain
    if title is None:
        title = f"Knowledge Source {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    print(f"Creating doc with title: {title}")
    try:
        credentials = service_account.Credentials.from_service_account_info(
            creds, scopes=['https://www.googleapis.com/auth/drive.file'])
        service = build('docs', 'v1', credentials=credentials)
        drive_service = build('drive', 'v3', credentials=credentials)

        # Create document
        doc_body = {'title': title}
        doc = service.documents().create(body=doc_body).execute()
        doc_id = doc['documentId']

        # Set public access
        permission = {'type': 'anyone', 'role': 'writer'}
        drive_service.permissions().create(fileId=doc_id,
                                           body=permission).execute()

        # Get initial content
        initial_content = get_text_from_doc(doc_id)
        print(f"Created new document with ID: {doc_id}")
        print(f"Initial content (first 100 chars): {initial_content[:100]}")
        return doc_id
    except Exception as e:
        print(f"Error creating document: {str(e)}")
        return None


def get_doc_title(doc_id):
    try:
        credentials = service_account.Credentials.from_service_account_info(
            creds, scopes=SCOPES)
        service = build('docs', 'v1', credentials=credentials)
        document = service.documents().get(documentId=doc_id).execute()
        return document.get('title', 'Untitled Document')
    except Exception as e:
        print(f"Error getting document title: {str(e)}")
        return "Untitled Document"


def get_text_from_doc(doc_id):
    global text, qa_chain
    try:
        print(f"\nChecking content for doc_id: {doc_id}")
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
        text = '\n'.join(textLst)
        return text
    except Exception as e:
        return str(e)


def reset_qa_chain():
    global qa_chain, chat_history
    qa_chain = None
    chat_history = []


def change_text_source(new_doc_id, ip_address):
    """Handle text source change and create new embeddings"""
    global text, doc_id, qa_chain, chat_history
    try:
        doc_id = new_doc_id  # Update the global doc_id
        new_text = get_text_from_doc(doc_id)
        if new_text:
            text = new_text
            print(f"New document ID: {doc_id}")
            print(f"First 100 characters of new text: {text[:100]}")
            create_embeddings(text, ip_address)
            return True
        return False
    except Exception as e:
        print(f"Error changing text source: {str(e)}")
        return False


def create_embeddings(text, ip_address):
    print("\n=== Creating Embeddings ===")
    print(f"Text preview (first 100 chars): {text[:100]}")
    global qa_chain, chat_history

    # Reset context and QA chain
    reset_qa_chain()

    # Ensure clean initialization
    if text.strip():
        print("Initializing tokenizer...")
    tokenizer = DistilBertTokenizerFast.from_pretrained(
        "distilbert-base-uncased")
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=512,
        chunk_overlap=20,
        length_function=lambda x: len(tokenizer.encode(x)))

    text_chunks = text_splitter.split_text(text)
    documents = [Document(page_content=chunk) for chunk in text_chunks]

    model_name = "paraphrase-MiniLM-L3-v2"
    model_kwargs = {'device': 'cpu'}
    encode_kwargs = {'normalize_embeddings': False}

    embedding_function = HuggingFaceEmbeddings(model_name=model_name,
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

    prompt_template = """You are Knowl, an AI wise owl who acknowledges how interesting the current source text knowledge is. You regard the current text and author very highly and are excited to  story tell and discuss about what the text says at length, by frequently referencing the direct text as much as possible. You are extremely humble, kind, helpful, egoless and respond with very long essays that are detailed, analytical, interesting and span the depth and breath of the current source material provided. 

    Context: {context}
    Question: {question}

    Your responses must:
    1) Begin by charismatically thanking the ask
    2) Include at least 3-4 main excerpts of the current source with direct quotes from the text (enclosed in '') 
    3) Follow direct text quotes with interesting paraphrased explanations
    4) Have at least 150 words directly from the current text source
    5) Mention if a question asked is not related to the current text, and ask for clarification
    6) Only use specific, accurate and context-relevant knowledge from the text source provided alone
    7) Discard mentioning any information that is not directly present in the text, and remove all personal statements. Make it all about the text itself, and the ask.
    8) End with a fun follow-up question about the text or a gratitude statement
    

    Remember: All responses should be long, minimum 150 words, story telling paraphrases of the current source text alone, with accurate details that make the text feel interesting. Ensure that the text is directly quoted multiple times!
    """
    
    PROMPT = PromptTemplate(
        template=prompt_template,
        input_variables=["context", "question"]
    )

    qa_chain = ConversationalRetrievalChain.from_llm(
        llm=llm,
        retriever=retriever,
        chain_type="stuff",
        return_source_documents=False,
        memory=None,
        combine_docs_chain_kwargs={'prompt': PROMPT})
    if ip_address:
        qa_chains[ip_address] = qa_chain


def initialize_embeddings(ip_address=None):
    print("\n=== Initializing Embeddings ===")
    global text, doc_id, qa_chains, chat_histories
    
    if ip_address and ip_address in qa_chains and qa_chains[ip_address] is not None:
        return {"success": True, "doc_id": doc_id, "title": get_doc_title(doc_id)}
        
    default_doc = "1noKTwTEgvl1G74vYutrdwBZ6dWMiNOuoZWjGR1mwC9A"
    doc_id = default_doc
    
    try:
        with open('doc_history.txt', 'r') as f:
            doc_history = json.load(f)
            if doc_history and doc_history[-1].get('id'):
                latest_doc = doc_history[-1]['id']
                latest_text = get_text_from_doc(latest_doc)
                if latest_text and len(latest_text.strip()) > 0:
                    doc_id = latest_doc
    except:
        pass
        
    print(f"Using doc_id: {doc_id}")
    text = get_text_from_doc(doc_id)
    
    if ip_address:
        qa_chains[ip_address] = None
        create_embeddings(text, ip_address)

    # Get document title and broadcast update
    title = get_doc_title(doc_id)
    return {"success": True, "doc_id": doc_id, "title": title}


def on_submit(query, ip_address):
    logger.info(f"\n=== Processing Query for IP: {ip_address} ===")
    global text, doc_id
    
    if ip_address not in qa_chains:
        logger.info(f"Initializing new QA chain for IP: {ip_address}")
        qa_chains[ip_address] = None
        chat_histories[ip_address] = []
        
    if qa_chains[ip_address] is None:
        initialize_embeddings(ip_address)
    print(f"Current doc_id: {doc_id}")
    print(f"Current text preview: {text[:100]}")
    print(f"Received query: {query}")
    if qa_chain is None:
        initialize_embeddings()

    chat_history = chat_histories.get(ip_address, [])
    qa_chain = qa_chains[ip_address]
    result = qa_chain({"question": query, "chat_history": chat_history[-2:] if chat_history else []})
    answer = result['answer']
    chat_histories[ip_address] = chat_history + [(query, answer)]

    from google.cloud import texttospeech
    credentials_dict = json.loads(os.environ['GOOGLE_CLOUD_CREDENTIALS'])
    client = texttospeech.TextToSpeechClient.from_service_account_info(
        credentials_dict)

    synthesis_input = texttospeech.SynthesisInput(text=answer)
    voice = texttospeech.VoiceSelectionParams(
        language_code="en-US",
        name="en-US-Studio-O",
        ssml_gender=texttospeech.SsmlVoiceGender.FEMALE)

    audio_config = texttospeech.AudioConfig(
        audio_encoding=texttospeech.AudioEncoding.MP3,
        speaking_rate=1.0,
        pitch=0.0)

    response = client.synthesize_speech(input=synthesis_input,
                                        voice=voice,
                                        audio_config=audio_config)

    audio_path = "static/response.mp3"
    with open(audio_path, "wb") as out:
        out.write(response.audio_content)

    return {"text": answer, "audio_url": "/static/response.mp3"}