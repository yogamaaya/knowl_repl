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

# Store QA chain sessions per IP address
qa_chains = {}
# Store minimal chat history
chat_histories = {}
# Store Google document IDs per IP
ip_documents = {}  
# Fallback document for initial load
DEFAULT_DOC_ID = '1noKTwTEgvl1G74vYutrdwBZ6dWMiNOuoZWjGR1mwC9A'

# Declare placeholders
text = ''
doc_id = ''

# Connect to Google Drive API
SCOPES = ['https://www.googleapis.com/auth/drive.readonly']
creds = json.loads(os.environ['GOOGLE_CREDENTIALS'])

# For better console logging
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
        if doc_id == DEFAULT_DOC_ID:
            return "Default Knowledge Base"
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


def change_text_source(new_doc_id, ip_address=None):
    """Handle text source change and create new embeddings"""
    global text, doc_id, ip_documents

    try:
        if not new_doc_id:
            print("Error: Invalid document ID")
            return False

        # Get document text
        try:
            new_text = get_text_from_doc(new_doc_id)
            if not new_text:
                print("Error: No text in new document")
                return False
        except Exception as e:
            print(f"Error getting text from new doc: {str(e)}")
            return False

        # Update globals and ensure IP document mapping persistence
        doc_id = new_doc_id
        text = new_text
        if ip_address:
            ip_documents[ip_address] = new_doc_id
            # Force create embeddings for new document
            create_embeddings(new_text, ip_address)
        print(f"New document ID: {doc_id}")
        print(f"First 100 characters of new text: {text[:100]}")

        # Create embeddings if IP provided
        if ip_address:
            try:
                create_embeddings(text, ip_address)
                if ip_address not in qa_chains or qa_chains[ip_address] is None:
                    print("Error: QA chain not properly initialized")
                    return False
                    
                # Save to document history after successful embedding creation
                title = get_doc_title(new_doc_id)
                save_doc_history(new_doc_id, title)
                
            except Exception as e:
                print(f"Error creating embeddings: {str(e)}")
                return False

        return True

    except Exception as e:
        print(f"Error changing text source: {str(e)}")
        return False


def save_doc_history(doc_id, title):
    try:
        # Ensure atomic file operations
        doc_history = []
        if os.path.exists('doc_history.txt'):
            try:
                with open('doc_history.txt', 'r') as f:
                    content = f.read().strip()
                    doc_history = json.loads(content) if content else []
            except (json.JSONDecodeError, FileNotFoundError):
                doc_history = []
        
        # Ensure doc_history is a list
        if not isinstance(doc_history, list):
            doc_history = []
            
        # Add new doc if not exists
        new_doc = {
            'id': doc_id,
            'title': title,
            'timestamp': datetime.now().isoformat()
        }
        
        if not any(d['id'] == doc_id for d in doc_history):
            doc_history.insert(0, new_doc)
            
        # Atomic write
        with open('doc_history.txt.tmp', 'w') as f:
            json.dump(doc_history, f, indent=2)
        os.replace('doc_history.txt.tmp', 'doc_history.txt')
            
        return True
    except Exception as e:
        print(f"Error saving doc history: {str(e)}")
        return False

def create_embeddings(text, ip_address=None):
    print("\n=== Creating Embeddings ===")
    print(f"Text preview (first 100 chars): {text[:100]}")
    global qa_chains, chat_histories

    if ip_address is None:
        return

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
    1) Begin by charismatically thanking the asker
    2) Include at least 3-4 main excerpts of the current source with direct quotes from the text (enclosed in '') 
    3) Follow direct text quotes with interesting paraphrased explanations
    4) Have at least 150 words directly from the current text source
    5) Mention if a question asked is not related to the current text, and ask for clarification
    6) Only use specific, accurate and context-relevant knowledge from the text source provided alone
    7) Discard mentioning any information that is not directly present in the text, and remove all personal statements. Make it all about the text itself, and the ask.
    8) End with a fun follow-up question about the text or a gratitude statement
    

    Remember: All responses should be long, minimum 150 words, story telling paraphrases of the current source text alone, with accurate details that make the text feel interesting. Ensure that the text is directly quoted multiple times!
    """

    PROMPT = PromptTemplate(template=prompt_template,
                            input_variables=["context", "question"])

    qa_chains[ip_address] = ConversationalRetrievalChain.from_llm(
        llm=llm,
        retriever=retriever,
        chain_type="stuff",
        return_source_documents=False,
        memory=None,
        combine_docs_chain_kwargs={'prompt': PROMPT})


def initialize_embeddings(ip_address=None):
    print("\n=== Initializing Embeddings ===")
    global text, doc_id, qa_chains, chat_histories, ip_documents

    try:
        # Initialize dictionaries if not exist or None
        qa_chains = qa_chains if isinstance(qa_chains, dict) else {}
        chat_histories = chat_histories if isinstance(chat_histories,
                                                      dict) else {}
        ip_documents = ip_documents if isinstance(ip_documents, dict) else {}

        # Use consistent document priority helper
        selected_doc_id = get_prioritized_doc_id(ip_address)
        if selected_doc_id != DEFAULT_DOC_ID:
            print(f"Using user's custom document: {selected_doc_id}")
        else:
            print(f"Using default document: {selected_doc_id}")

        # Only update global doc_id if it's a new IP or doesn't have existing document
        if not (ip_address and ip_address in ip_documents):
            doc_id = selected_doc_id
            if ip_address:
                ip_documents[ip_address] = selected_doc_id

        # Get document text
        try:
            text = get_text_from_doc(doc_id)
            if not text:
                print("Error: No text retrieved from document")
                return False
            print(f"Retrieved text (first 100 chars): {text[:100]}")
        except Exception as e:
            print(f"Error getting text from doc: {str(e)}")
            return False

        # Create embeddings for IP if needed
        if ip_address:
            if ip_address not in qa_chains:
                try:
                    create_embeddings(text, ip_address)
                    if ip_address not in qa_chains or qa_chains[
                            ip_address] is None:
                        print("Error: QA chain not properly initialized")
                        return False
                except Exception as e:
                    print(f"Error creating embeddings: {str(e)}")
                    return False
            else:
                print(f"Using existing embeddings for IP: {ip_address}")

        return True

    except Exception as e:
        print(f"Initialization error: {str(e)}")
        return False


def on_submit(query, ip_address):
    logger.info(f"\n=== Processing Query for IP: {ip_address} ===")
    global text, doc_id, qa_chains

    # Ensure qa_chains exists
    if not isinstance(qa_chains, dict):
        qa_chains = {}

    # Initialize or reinitialize if needed
    max_retries = 3
    retries = 0

    while (ip_address not in qa_chains
           or qa_chains[ip_address] is None) and retries < max_retries:
        logger.info(
            f"Attempt {retries + 1}/{max_retries} to initialize QA chain for IP: {ip_address}"
        )
        success = initialize_embeddings(ip_address)

        if success and ip_address in qa_chains and qa_chains[
                ip_address] is not None:
            break

        retries += 1
        if retries == max_retries:
            raise Exception(
                "Failed to initialize QA chain after multiple attempts")

    chat_histories.setdefault(ip_address, [])

    print(f"Current doc_id: {doc_id}")
    print(f"Current text preview: {text[:100]}")
    print(f"Received query: {query}")

    chat_history = chat_histories.get(ip_address, [])
    try:
        if not qa_chains[ip_address]:
            return {
                "text":
                "I apologize, but I'm having trouble processing your request. Please try changing the text source by clicking the 'Change Text Source' button above and paste your text into the Google Doc that opens.",
                "audio_url": None
            }
        result = qa_chains[ip_address]({
            "question":
            query,
            "chat_history":
            chat_history[-2:] if chat_history else []
        })
        answer = result['answer']
    except (TypeError, AttributeError) as e:
        logger.error(f"QA chain error: {str(e)}")
        return {
            "text":
            "I apologize, but I'm having trouble processing your request. Please try changing the text source by clicking the 'Change Text Source' button above and paste your text into the Google Doc that opens.",
            "audio_url": None
        }

    # Update chat history before TTS generation
    updated_history = chat_history + [(query, answer)]
    chat_histories[ip_address] = updated_history

    # Only generate TTS for latest message
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
def get_prioritized_doc_id(ip_address):
    """Helper function to consistently determine document priority"""
    if ip_address and ip_address in ip_documents:
        doc_id = ip_documents[ip_address]
        if doc_id:  # If any document exists for this IP, use it
            return doc_id
    # Only use default for completely new sessions
    return DEFAULT_DOC_ID
