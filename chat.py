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

# import requests
# from bs4 import BeautifulSoup

# Load environment variables
load_dotenv()
openai_api_key = os.getenv('OPENAI_API_KEY')

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
        text = []
        # Changed doc_content to document.get('body', {}).get('content', [])
        for element in document.get('body', {}).get('content', []):
            if 'paragraph' in element:
                line_content = ''
                for para_element in element['paragraph']['elements']:
                    if 'textRun' in para_element:
                        line_content += para_element['textRun']['content']
                if line_content.strip():  # Only add non-empty lines
                    text.append(line_content)

        return '\n'.join(text)
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

    # Configure OpenAI for fast, detailed responses
    llm = OpenAI(
        temperature=0.2,
        max_tokens=1500,  # Increased for longer essays
        model="gpt-3.5-turbo-instruct",  # Fast model
        presence_penalty=0.0,  # Small increase to encourage diverse content
    )

    # Create a new Chroma database and QA chain
    db = Chroma.from_documents(documents, embedding_function)

    # Optimize QA chain for speed and detail
    retriever = db.as_retriever(search_kwargs={"k": 2})
    prompt_template = PromptTemplate(
        input_variables=["question", "context"],
        template=
        """As a kind, friendly and empathetic assistant, write an insightful summary essay (minimum 300 words) that:
        1. Opens with an engaging introduction acknowledging the thoughtfulness of the question
        2. Develops at least 3-4 main points with detailed explanations
        3. Uses multiple direct quotes from the text, always enclosed in single quotes ''
        4. Provides thorough analysis (100-150 words) after each quote
        5. Maintains clear paragraph structure with proper transitions
        6. Includes examples and specific details from the text
        7. Concludes with a substantive summary and thank you

        Important:
        - Ensure the response is at least 500 words
        - Add appropiate line breaks to separate paragraphs
        - Include at least 4-5 relevant quotes from the text
        - Support each main point with detailed analysis
        - Use clear topic sentences and transitions between paragraphs
        - Provide comprehensive explanations and examples
        - End with a well-developed conclusion that is complete and ends in a full stop

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
    answer = result['answer']
    chat_history.append((query, answer))

    # Generate audio using Google Cloud Text-to-Speech
    from google.cloud import texttospeech
    import json
    import os

    # Initialize Text-to-Speech client
    credentials_dict = json.loads(os.environ['GOOGLE_CLOUD_CREDENTIALS'])
    client = texttospeech.TextToSpeechClient.from_service_account_info(
        credentials_dict)

    synthesis_input = texttospeech.SynthesisInput(text=answer)

    # Configure voice parameters
    voice = texttospeech.VoiceSelectionParams(
        language_code="en-US",
        name="en-US-Studio-O",  # A natural-sounding female voice
        ssml_gender=texttospeech.SsmlVoiceGender.FEMALE)

    # Select the type of audio file
    audio_config = texttospeech.AudioConfig(
        audio_encoding=texttospeech.AudioEncoding.MP3,
        speaking_rate=1.0,
        pitch=0.0)

    # Perform the text-to-speech request
    response = client.synthesize_speech(input=synthesis_input,
                                        voice=voice,
                                        audio_config=audio_config)

    # Save the audio file
    audio_path = "static/response.mp3"
    with open(audio_path, "wb") as out:
        out.write(response.audio_content)

    return {"text": answer, "audio_url": "/static/response.mp3"}
