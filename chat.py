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

from flask import session
chat_histories = {}  # Store histories per IP
message_histories = {}  # Store message histories per IP
text = ''
doc_id = ''
qa_chains = {}  # Store chains per IP
SCOPES = ['https://www.googleapis.com/auth/drive.readonly']
creds = json.loads(os.environ['GOOGLE_CREDENTIALS'])


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


def change_text_source(new_doc_id):
    """Handle text source change and create new embeddings"""
    global text, doc_id, qa_chain, chat_history
    try:
        doc_id = new_doc_id  # Update the global doc_id
        new_text = get_text_from_doc(doc_id)
        if new_text:
            text = new_text
            print(f"New document ID: {doc_id}")
            print(f"First 100 characters of new text: {text[:100]}")
            create_embeddings(text)
            return True
        return False
    except Exception as e:
        print(f"Error changing text source: {str(e)}")
        return False


def create_embeddings(text):
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

    prompt_template = """
    You are a kind, egoless, humble, smart and helpful friend of the curious ask. Your name is Knowl because you are as wise as an owl. You are here to help people understand the current text better and gain deep insights. You are professional and knowledgeable who only gives accurate, long and detailed analytical responses related to the current text in complete sentences. You will get the person to be intersted in getting to know the current text as much as possible!

    Context: {context}
    Question: {question}

    All responses you give have at least 150 words based on the present context alone. You only respond with knowledge related to the current text with mutliple related direct quotes. All your responses are accurate, detailed, long and analytical which:
    1) first charismatically express thanks for asking. 
    2) have accurate details according to the current text, with 3-4 direct quotes from the current text enclosed in ''.
    3) have direct excerpts from the text followed by a simple summary explanation.
    4) invoke curiosity in the user to learn more about the current text.
    5) have 3-4 main points directly from the text being highlighted.
    6) apart from having direct quotes, are always paraphrased sentences of the current text only.
    7) have only information present directly in the current text alone.
    8) acknowledges if a question asked is not in the current text, and clarifies that the information is taken from outside the current context.
    8) end with either a thought provoking question to keep the conversation going about the current topic or a gratitude filled closing statement.
    """

    PROMPT = PromptTemplate(template=prompt_template,
                            input_variables=["context", "question"])

    qa_chain = ConversationalRetrievalChain.from_llm(
        llm=llm,
        retriever=retriever,
        chain_type="stuff",
        return_source_documents=False,
        memory=None,
        combine_docs_chain_kwargs={'prompt': PROMPT})


def initialize_embeddings():
    print("\n=== Initializing Default Embeddings ===")
    global text, doc_id, qa_chain
    doc_id = "1noKTwTEgvl1G74vYutrdwBZ6dWMiNOuoZWjGR1mwC9A"
    print(f"Using default doc_id: {doc_id}")
    text = get_text_from_doc(doc_id)
    print(f"Retrieved text (first 100 chars): {text[:100]}")
    qa_chain = None
    create_embeddings(text)


def on_submit(query, ip_address):
    print("\n=== Processing Query ===")
    if ip_address not in chat_histories:
        chat_histories[ip_address] = []
    if ip_address not in message_histories:
        message_histories[ip_address] = []
    if ip_address not in qa_chains:
        qa_chains[ip_address] = None
    
    global text, doc_id
    print(f"Current doc_id: {doc_id}")
    print(f"Current text preview: {text[:100]}")
    print(f"Received query: {query}")
    if qa_chain is None:
        initialize_embeddings()

    result = qa_chain({"question": query, "chat_history": chat_history[-2:]})
    answer = result['answer']
    chat_history.append((query, answer))

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
