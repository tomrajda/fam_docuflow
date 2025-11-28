# Standard libraries and environment patch
import os
import sys
import traceback

__import__('pysqlite3')
import pysqlite3 as sqlite3
sys.modules['sqlite3'] = sqlite3

# External libraries
import boto3
import pytesseract
from pdf2image import convert_from_path
from PIL import ImageOps

# Vector Database libraries
from chromadb import HttpClient

# LangChain libraries
# Loaders
from langchain_community.document_loaders import PyPDFLoader, TextLoader

# Text Splitters
from langchain.text_splitter import RecursiveCharacterTextSplitter

# Embeddings
from langchain_google_genai import GoogleGenerativeAIEmbeddings

# Vector Stores
from langchain_community.vectorstores import Chroma

# Environment Variables
MINIO_ENDPOINT = os.getenv("MINIO_ENDPOINT")
MINIO_ACCESS_KEY = os.getenv("MINIO_ACCESS_KEY")
MINIO_SECRET_KEY = os.getenv("MINIO_SECRET_KEY")
MINIO_BUCKET_NAME = os.getenv("MINIO_BUCKET_NAME","docuflow-files")
CHROMA_HOST = os.getenv("CHROMA_HOST")
CHROMA_PORT = int(os.getenv("CHROMA_PORT"))

# MinIO/S3 CLient initializaton
s3_client = boto3.client(
    's3',
    endpoint_url=MINIO_ENDPOINT,
    aws_access_key_id=MINIO_ACCESS_KEY,
    aws_secret_access_key=MINIO_SECRET_KEY,
    config=boto3.session.Config(signature_version='s3v4'),
    verify=False
)

# Client initialization for connection to ChromaDB server
chroma_client = HttpClient(host=CHROMA_HOST, port=CHROMA_PORT)

def ocr_pdf_to_text(pdf_path: str, output_txt_path: str):
    """
    Performs OCR on a PDF file
    and saves the extracted text 
    to a TXT file.
    
    :param pdf_path: Path to inpt PDF file
    :type pdf_path: str
    :param output_txt_path: Path to otpt TXT file
    :type output_txt_path: str
    """

    print(f"OCR: Starting visual processing for {pdf_path}...")
    try:
        # Image conversion (DPI 300)
        images = convert_from_path(pdf_path, dpi=300) 
        full_text = ""
        
        for i, image in enumerate(images):
            
            # Image conversion to grayscale (SAFE!)
            gray_image = image.convert('L')
            
            # Auto contrast (for better quality)
            enhanced_image = ImageOps.autocontrast(gray_image)

            # OCR
            # PSM (Page Segmentation Mode) 3, Polish + English
            text = pytesseract.image_to_string(enhanced_image, lang='pol+eng')
            
            full_text += text + "\n"
            print(f"OCR: Page {i+1} processed.")
            
        with open(output_txt_path, "w", encoding="utf-8") as f:
            f.write(full_text)
            
        return True
    except Exception as e:
        print(f"OCR Error: {e}")
        return False

def process_document_job(file_id: str, category: str, file_path: str):
    """
    Main process to handle document processing job.
    
    :param file_id: File identifier
    :type file_id: str
    :param category: Document category
    :type category: str
    :param file_path: File path in MinIO/S3
    :type file_path: str
    """

    # Verify Google API Key
    GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")

    if not GOOGLE_API_KEY:
        print("Error: GOOGLE_API_KEY environment variable not set.")
        return False
        
    TEMP_PDF_PATH = f"/tmp/{file_id}_temp.pdf"
    TEMP_TXT_PATH = f"/tmp/{file_id}.txt"

    try:

        print(f"JOB STARTED: Processing document {file_id} in category {category}")
        
        # Download file from S3 to TEMP
        print(f"Downloading from MinIO: {file_path}")
        s3_client.download_file(MINIO_BUCKET_NAME, file_path, TEMP_PDF_PATH)
        
        # Load as text PDF
        loader = PyPDFLoader(TEMP_PDF_PATH)
        documents = loader.load()

        # Check whether meaningful text extracted
        raw_text_content = "".join([doc.page_content for doc in documents])
        
        if len(raw_text_content.strip()) < 50:
            print("A Scan document (little text) has been detected. Running OCR...")
            
            if ocr_pdf_to_text(TEMP_PDF_PATH, TEMP_TXT_PATH):
                # If OCR successful, load the resulting TXT file instead of PDF
                loader = TextLoader(TEMP_TXT_PATH, encoding="utf-8")
                documents = loader.load()

                print(f"OCR completed. Text loaded from {TEMP_TXT_PATH}")

            else:
                print("OCR failed. Using an empty/original PDF.")

        else:
            print("OCR omitted. Document contains a text layer.")

        # Chunking
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1200, 
            chunk_overlap=400,
            separators=["\n\n", "\n", " ", ""]
        )
        texts = text_splitter.split_documents(documents)
        
        # Assign Metadata to each fragment
        for doc in texts:
            doc.metadata["category"] = category
            doc.metadata["file_id"] = file_id 

        # Embeddings initialization
        embeddings = GoogleGenerativeAIEmbeddings(
            model="models/embedding-001", 
            api_key=GOOGLE_API_KEY 
        )
        
        # Save embeddings to ChromaDB vector store
        # Creating a ChromaDB instance with a client
        MASTER_COLLECTION_NAME = os.getenv("MASTER_COLLECTION_NAME", "docuflow_master_index")

        vector_store = Chroma(
            client=chroma_client,
            collection_name=MASTER_COLLECTION_NAME, 
            embedding_function=embeddings
        )

        # Add documents to vector store collection 
        vector_store.add_documents(texts) 

        print(f"Document {file_id} indexed into {MASTER_COLLECTION_NAME} successfuly.")
        
    except Exception as e:

        print(f"Error: Job failed for {file_id}: {e}")
        traceback.print_exc()
        
        return False
    
    finally:
        
        # Clear temporary files
        if os.path.exists(TEMP_PDF_PATH):
            os.remove(TEMP_PDF_PATH)
        if os.path.exists(TEMP_TXT_PATH):
            os.remove(TEMP_TXT_PATH)

    return True

if __name__ == "__main__":

    # Local tests
    test_file_id = "825e843d-b1e3-411b-8f3b-dee4f5e3036d"
    test_category = "Umowy"
    test_file_path = "/home/tomek/Projekty/docuflow-project/shared_files/" \
                    "825e843d-b1e3-411b-8f3b-dee4f5e3036d.pdf"
    process_document_job(test_file_id, test_category, test_file_path)
    