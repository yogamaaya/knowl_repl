
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
from langchain.prompts import PromptTemplate
from datetime import datetime

load_dotenv()
openai_api_key = os.getenv('OPENAI_API_KEY')

chat_history = []
text = ''
doc_id = ''
qa_chain = None
SCOPES = ['https://www.googleapis.com/auth/drive.readonly']
creds = json.loads(os.environ['GOOGLE_CREDENTIALS'])

def create_embeddings(text):
    global qa_chain
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

    embedding_function = HuggingFaceEmbeddings(model_name=model_name,
                                               model_kwargs=model_kwargs,
                                               encode_kwargs=encode_kwargs)

    llm = OpenAI(
        temperature=0.1,
        max_tokens=300,
        model="gpt-3.5-turbo-instruct",
        presence_penalty=0,
    )

    db = Chroma.from_documents(documents, embedding_function)
    retriever = db.as_retriever(search_kwargs={"k": 2})
    prompt_template = PromptTemplate(
        input_variables=["question", "context"],
        template="""As a kind, friendly and empathetic assistant, acknowledge the thoughtfulness of the question. 
        Then provide a long and detailed response that:
        1. Starts with a simple kind acknowledgement.
        2. Stays strictly focused on the given context only.
        3. Includes a few direct quote sentences within the long answer, enclosed within ''.
        5. Provides explanation and analysis after each quote.
        6. Ends always with a concluding thank you and a full stop.

        Remember: Every fact or claim must be supported by a direct quote from the text.

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

def create_new_doc():
    global doc_id
    try:
        credentials = service_account.Credentials.from_service_account_info(
            creds,
            scopes=[
                'https://www.googleapis.com/auth/drive.file',
                'https://www.googleapis.com/auth/documents',
                'https://www.googleapis.com/auth/drive'
            ])
        service = build('docs', 'v1', credentials=credentials)
        drive_service = build('drive', 'v3', credentials=credentials)

        doc = drive_service.files().create(
            body={
                'name': f'Knowl Text Source {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}',
                'mimeType': 'application/vnd.google-apps.document'
            }).execute()

        drive_service.permissions().create(
            fileId=doc['id'],
            body={
                'type': 'anyone',
                'role': 'writer',
                'allowFileDiscovery': False
            }).execute()
        
        doc_id = doc['id']
        return doc_id
    except Exception as e:
        print(f"Error creating doc: {e}")
        return None

def updateText():
    global doc_id, text
    if not doc_id:
        doc_id = "1noKTwTEgvl1G74vYutrdwBZ6dWMiNOuoZWjGR1mwC9A"
    try:
        credentials = service_account.Credentials.from_service_account_info(
            creds, scopes=SCOPES)
        service = build('docs', 'v1', credentials=credentials)
        document = service.documents().get(documentId=doc_id).execute()
        text = ''
        content = document.get('body', {}).get('content', [])
        if not content:
            return "Please paste your text into the Google Doc and try again."

        for element in content:
            if 'paragraph' in element:
                for para_element in element['paragraph']['elements']:
                    if 'textRun' in para_element:
                        text += para_element['textRun']['content']

        if not text.strip():
            return "Please paste your text into the Google Doc and try again."

        create_embeddings(text)
        return text
    except Exception as e:
        return str(e)

def on_submit(query):
    global chat_history, text, qa_chain

    if not qa_chain or query == 'CREATE_NEW_DOC':
        text = updateText()
        if isinstance(text, str) and text.startswith("Please paste your text"):
            return {'text': text, 'audio_url': None}

    if query == 'CREATE_NEW_DOC':
        doc_id = create_new_doc()
        return {'doc_id': doc_id}

    result = qa_chain({"question": query, "chat_history": chat_history[-2:]})
    answer = result['answer']
    chat_history.append((query, answer))

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
