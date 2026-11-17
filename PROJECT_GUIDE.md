# Uzhavan Farmer Scheme Assistant

This guide explains the project architecture, setup, run commands, and the normal
document-ingestion and chat workflows in one place.

## What the application does

The assistant answers questions about Tamil Nadu government agricultural
schemes using information retrieved from documents that have been indexed.
Its two pipelines are:

1. **Document ingestion:** upload an official PDF or explicitly scrape one of
   the approved government webpages, then process it into the local FAISS index.
2. **Question answering:** retrieve relevant indexed chunks, send those excerpts
   to the language model, and return an answer with source references.

The index is not rebuilt when the app starts. New documents are added only when
the user clicks **Process documents**.

## Architecture diagrams

- [System pipeline diagram](./pipeline-flow.svg) — application and ingestion
  flow in a left-to-right layout.
- [Pipeline architecture diagram](./pipeline-architecture.svg) — ingestion and
  grounded question-answering stages.

## Technology used

| Area | Technology | Purpose |
|---|---|---|
| User interface | Streamlit | PDF upload, approved-source selection, ingestion status, chat |
| API | FastAPI and Uvicorn | Receives frontend requests and serves upload, scraping, ingestion, and chat endpoints |
| Website extraction | Playwright for Python | Loads and extracts readable text from approved webpages |
| PDF extraction | PyMuPDF | Extracts text page by page and preserves page numbers |
| Text splitting | LangChain `RecursiveCharacterTextSplitter` | Splits extracted text into searchable chunks |
| Embeddings | OpenAI `text-embedding-3-small` | Converts document chunks and user questions into vectors |
| Vector store | FAISS CPU | Stores vectors locally and retrieves similar chunks |
| Chat model | OpenAI `gpt-4o-mini` by default | Produces a farmer-friendly response from retrieved context |
| HTTP client | Requests | Connects the Streamlit frontend to FastAPI |
| Local configuration | `.env` and `python-dotenv` | Loads the OpenAI API key without putting it in source code |
| Validation | Pydantic | Validates API request and response data |

Dependencies are listed in [requirements.txt](./requirements.txt).

## Project layout

```text
app.py                         Streamlit frontend
backend/
  main.py                      FastAPI application and startup
  routes/
    upload.py                  PDF upload endpoint
    scraping.py                Approved website scrape endpoint
    ingestion.py               Process and status endpoints
    chat.py                    RAG question-answer endpoint
services/
  pdf_loader.py                PDF validation, extraction, and file naming
  web_scraper.py               Approved-source checks and Playwright extraction
  text_splitter.py             Text chunking
  embedding_service.py         OpenAI embeddings configuration
  vector_store.py              FAISS load, update, and persistence
  ingestion_service.py         Coordinates PDF and website ingestion
  retrieval_service.py         FAISS retrieval and source citation preparation
  llm_service.py               Grounded OpenAI response generation
  storage.py                   Local data directories and JSON document registry
models/
  schemas.py                   API request and response models
data/
  uploaded_pdfs/               Uploaded PDFs awaiting or completing ingestion
  scraped_documents/           Scraped page text awaiting or completing ingestion
  faiss_index/                 Persisted FAISS index files
  metadata/documents.json      Processed-document registry
tests/                         Unit tests for upload, scraping, retrieval, and API
```

Generated files under `data/`, local environments, and `.env` are excluded by
[.gitignore](./.gitignore). Keep `requirements.txt` and `.env.example` in source
control; do not commit `.env` or an API key.

## Prerequisites

- Python 3.10 or later.
- An OpenAI API key with access to the configured embedding and chat models.
- Playwright's Chromium browser for website scraping.
- Permission from your IT administrator to install and run project dependencies.

### Windows application-control note

On this machine, Windows Application Control blocked the native FAISS DLL
(`_swigfaiss`). Reinstalling or restarting on Windows does not override that
policy. IT approved using WSL/Ubuntu for this project. Use a Linux virtual
environment there; the Windows `.venv` cannot be used by Linux.

## Setup in Ubuntu / WSL

Open an Ubuntu terminal in VS Code. Run the following from the project directory
as shown:

```bash
cd /mnt/d/Thamarai/Assignment/Buildathon/UzhavanRAG
sudo apt update
sudo apt install -y python3-venv python3-pip
python3 -m venv ~/.venvs/uzhavan-rag
source ~/.venvs/uzhavan-rag/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m playwright install --with-deps chromium
```

Verify that Linux FAISS loads:

```bash
python -c "import faiss; print('FAISS is ready')"
```

Expected output:

```text
FAISS is ready
```

If a policy blocks an install or library, stop and ask IT to approve it. Do not
rename, copy, or otherwise work around a blocked executable or library.

## Configure the API key

Create or edit the `.env` file in the project root (next to `app.py`).
`.env.example` shows the expected key name. Add a valid key locally:

```env
OPENAI_API_KEY=your_actual_key_here
```

Do not paste the key into chat, screenshots, source code, or a committed file.
OpenAI API calls for embeddings and chat may incur charges.

## Start the application

Stop other copies of this project's Windows or WSL servers first if they are
already using the same ports. Start both services from the project directory
with the Ubuntu virtual environment activated.

### Terminal 1 — FastAPI

```bash
cd /mnt/d/Thamarai/Assignment/Buildathon/UzhavanRAG
source ~/.venvs/uzhavan-rag/bin/activate
python -m uvicorn backend.main:app --reload --port 8000
```

Keep the terminal open. FastAPI's interactive API page is at
<http://127.0.0.1:8000/docs>.

### Terminal 2 — Streamlit

Open a second Ubuntu terminal:

```bash
cd /mnt/d/Thamarai/Assignment/Buildathon/UzhavanRAG
source ~/.venvs/uzhavan-rag/bin/activate
export BACKEND_URL=http://127.0.0.1:8000
python -m streamlit run app.py --server.port 8501
```

Open <http://localhost:8501> in a browser. If a port is already in use, choose a
free port (for example `8502`). If FastAPI is moved to another port, set
`BACKEND_URL` in the Streamlit terminal to match it before starting Streamlit.
If WSL cannot launch a browser automatically, open the printed localhost URL
yourself.

## Ingest PDFs and government webpages

1. In Streamlit, select one or more official scheme PDFs and click **Upload
   selected PDFs**. Files are staged in `data/uploaded_pdfs/`.
2. Or choose one of the configured official webpages and click **Scrape selected
   website**. Extracted text is staged in `data/scraped_documents/`.
3. Click **Process documents**. This extracts/loads the staged text, splits it
   into chunks, adds source metadata, generates embeddings, and appends the
   vectors to FAISS.
4. Check **Ingestion status** for processed documents, pending documents, chunk
   count, and FAISS availability.
5. After processing is complete, ask a question in the chat.

Scraping is allowlisted to these URLs only:

- <https://aed.tn.gov.in/en/individual-based-subsidy-schemes/>
- <https://www.landreforms.tn.gov.in/UPT.html>

The scraper checks the website's `robots.txt`, keeps browser requests on the
approved host, and does not bypass authentication, CAPTCHA, or access controls.
It scrapes the selected page, not every linked page on the website. Respect the
sites' terms and policies.

### PDF processing details

- Only PDF files with a PDF signature are accepted; the upload limit is 20 MB.
- PyMuPDF extracts text page by page. Empty-text pages are skipped.
- The default chunk size is 1,000 characters with 150 characters of overlap.
- PDF chunks preserve the source filename and page number.
- Website chunks preserve the page title, official URL, department, and document
  type. Websites do not have PDF page numbers.
- Document contents are hashed to skip duplicate ingestion.
- New vectors are added to the existing index; starting either service does not
  trigger ingestion.

The local data directory should be backed up if it must survive a disk loss. The
FAISS loader uses local deserialization; only load index files created by this
project and stored in a location you trust.

## Ask questions

The chat UI sends the current question and recent conversation history to
`POST /chat`.

1. The backend embeds the question and searches the FAISS index for the top 5
   chunks.
2. It builds a context of up to 16,000 characters and associates source IDs with
   document names, PDF pages, and website URLs.
3. The `gpt-4o-mini` model receives the question, recent history, and retrieved
   excerpts. Its prompt asks it to answer in the question's language, use only
   those excerpts, cite supporting source IDs, and say when the excerpts do not
   contain enough information.
4. Streamlit displays the answer and source references.

An empty index returns an unavailable-information message without calling the
chat model. Prompt instructions reduce unsupported answers but cannot guarantee
that a generative model will never make a mistake; verify consequential
eligibility, amount, and deadline information against the cited official source.

## API endpoints

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/upload-pdf` | Validate and stage a PDF upload |
| `POST` | `/scrape-website` | Scrape and stage one allowlisted webpage |
| `POST` | `/process-documents` | Process pending PDFs and scraped pages into FAISS |
| `GET` | `/ingestion-status` | Return pending/processed counts and index status |
| `GET` | `/documents` | List processed document summaries |
| `POST` | `/chat` | Retrieve chunks and generate an answer with sources |
| `GET` | `/health` | Check whether FastAPI is responding |

Use <http://127.0.0.1:8000/docs> to inspect and manually exercise the API.
`/scrape-website` and `/chat` require `POST`; entering those paths directly in
the browser sends `GET` and returns “Method Not Allowed”.

## Troubleshooting

### Port already in use

Choose another free port. For example, run FastAPI with `--port 8001`, then set
`export BACKEND_URL=http://127.0.0.1:8001` in the Streamlit terminal before
starting the frontend.

### Playwright package or Chromium missing

With the project's Ubuntu virtual environment activated:

```bash
python -m pip install -r requirements.txt
python -m playwright install --with-deps chromium
```

Restart FastAPI after installing packages.

### Missing `langchain_core`

With the correct virtual environment activated, install requirements:

```bash
python -m pip install -r requirements.txt
```

### OpenAI API key error

Check that the project-root `.env` contains `OPENAI_API_KEY=...`, with a valid
key. Never print or share the key. Restart FastAPI after changing environment
configuration.

### FAISS import or native-library error

On Windows, this project environment encountered an Application Control block
on the FAISS native DLL. Run the approved WSL environment and check FAISS with
`python -c "import faiss; print('FAISS is ready')"` there. If Ubuntu is also
blocked, ask IT to approve the dependency; do not work around the block.

### Processing returns HTTP 500

Read the complete traceback in the terminal running Uvicorn. The last exception
usually identifies the dependency, API, or storage operation that failed. Do
not share `.env` contents or API keys when sharing logs.

## Tests

The tests use Python's built-in `unittest` runner and mock external model calls:

```bash
python -m unittest discover -s tests -v
```

This validates unit-level upload, scraping policy, ingestion, retrieval,
citations, and API behavior. It does not by itself verify a live OpenAI request,
live website scraping, or a real persisted FAISS rebuild; those require the
dependencies, credentials, and runtime access described above.
