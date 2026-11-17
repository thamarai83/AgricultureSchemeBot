
import streamlit as st
import requests
import os

BACKEND_URL = os.getenv("BACKEND_URL", "http://127.0.0.1:8000").rstrip("/")


def api_error_message(error: requests.RequestException) -> str:
    response = getattr(error, "response", None)
    if response is not None:
        try:
            detail = response.json().get("detail")
        except ValueError:
            detail = None
        if isinstance(detail, str) and detail:
            return detail
    return str(error)


st.set_page_config(
    page_title="Uzhavan AI Assistant",
    page_icon="🌾",
    layout="wide"
)

st.title("🌾 Uzhavan AI Farmer Scheme Assistant")

st.caption(
    "Tamil Nadu Government Agricultural Scheme Information Assistant"
)

# Two-column layout
left, right = st.columns([1, 2])

# LEFT PANEL
with left:
    st.subheader("📂 Document Management")

    uploaded_files = st.file_uploader(
        "Select government scheme PDFs",
        type=["pdf"],
        accept_multiple_files=True,
    )

    if st.button("Upload selected PDFs", disabled=not uploaded_files):
        for uploaded_file in uploaded_files:
            try:
                response = requests.post(
                    f"{BACKEND_URL}/upload-pdf",
                    files={
                        "file": (
                            uploaded_file.name,
                            uploaded_file.getvalue(),
                            "application/pdf",
                        )
                    },
                    timeout=30,
                )
                response.raise_for_status()
            except requests.RequestException as exc:
                st.error(f"Could not upload {uploaded_file.name}: {exc}")
                break
            st.success(f"Uploaded: {uploaded_file.name}")

    st.divider()

    st.subheader("🌐 Scrape an approved government page")
    website_url = st.selectbox(
        "Choose a Tamil Nadu government source",
        [
            "https://aed.tn.gov.in/en/individual-based-subsidy-schemes/",
            "https://www.landreforms.tn.gov.in/UPT.html",
        ],
        format_func=lambda url: (
            "Agricultural Engineering Department — subsidy schemes"
            if "aed.tn.gov.in" in url
            else "Land Reforms Department — Uzhavar Pathukappu Thittam"
        ),
        key="website_source",
    )

    if st.button("Scrape selected website"):
        try:
            response = requests.post(
                f"{BACKEND_URL}/scrape-website",
                json={"url": website_url},
                timeout=60,
            )
            response.raise_for_status()
            result = response.json()
        except requests.RequestException as exc:
            st.error(f"Website scraping failed: {api_error_message(exc)}")
        else:
            st.success(
                f"Scraped {result['document_name']} "
                f"({result['characters_extracted']} characters)."
            )
            st.info("Click Process documents to add this page to the FAISS index.")

    st.divider()

    st.subheader("📄 Process pending documents")
    if st.button("Process documents"):
        try:
            response = requests.post(
                f"{BACKEND_URL}/process-documents",
                timeout=300,
            )
            response.raise_for_status()
            result = response.json()
        except requests.RequestException as exc:
            st.error(f"Document processing failed: {api_error_message(exc)}")
        else:
            st.success(
                f"Processed {result['processed_documents']} document(s) "
                f"and created {result['chunks_created']} chunk(s)."
            )
            if result["duplicates_skipped"]:
                st.info(
                    f"Skipped {result['duplicates_skipped']} duplicate upload(s)."
                )

    st.divider()

    st.subheader("📊 Ingestion status")
    try:
        status_response = requests.get(
            f"{BACKEND_URL}/ingestion-status",
            timeout=5,
        )
        status_response.raise_for_status()
        ingestion_status = status_response.json()
    except requests.RequestException as exc:
        st.error(f"Could not load ingestion status: {api_error_message(exc)}")
    else:
        st.write(f"Processed documents: {ingestion_status['processed_documents']}")
        st.write(f"Pending documents: {ingestion_status['pending_documents']}")
        st.write(f"Text chunks: {ingestion_status['total_chunks']}")
        st.write(
            "FAISS index: "
            + ("available" if ingestion_status["faiss_available"] else "not created")
        )
        if ingestion_status["documents"]:
            st.write("Processed files")
            for document in ingestion_status["documents"]:
                st.caption(
                    f"{document['document_name']} "
                    f"({document['document_type']}) — "
                    f"{document['chunk_count']} chunks"
                )

# RIGHT PANEL
with right:
    st.subheader("💬 Ask Uzhavan AI")

    st.write("Ask about schemes in your processed PDFs and approved webpages.")

    if "messages" not in st.session_state:
        st.session_state.messages = []

    if st.button("Clear chat", key="clear_chat", icon=":material/delete_sweep:"):
        st.session_state.messages = []

    for message_index, message in enumerate(st.session_state.messages):
        with st.chat_message(message["role"]):
            st.write(message["content"])
            for source in message.get("sources", []):
                citation = source["document_name"]
                if source.get("page_number") is not None:
                    citation += f", page {source['page_number']}"
                st.caption(f"[{source['source_id']}] {citation}")
                if source.get("source_url"):
                    st.link_button(
                        "Open source website",
                        source["source_url"],
                        key=f"source-link-{message_index}-{source['source_id']}",
                    )

    question = st.chat_input(
        "Ask your question in Tamil or English...",
        submit_mode="disable",
    )

    if question:
        history = [
            {"role": message["role"], "content": message["content"]}
            for message in st.session_state.messages[-8:]
        ]
        st.session_state.messages.append({
            "role": "user",
            "content": question
        })

        with st.chat_message("user"):
            st.write(question)

        with st.chat_message("assistant"):
            with st.spinner("Searching your indexed government documents..."):
                try:
                    response = requests.post(
                        f"{BACKEND_URL}/chat",
                        json={"question": question, "history": history},
                        timeout=90,
                    )
                    response.raise_for_status()
                    result = response.json()
                except requests.HTTPError as exc:
                    detail = None
                    if exc.response is not None:
                        try:
                            detail = exc.response.json().get("detail")
                        except requests.JSONDecodeError:
                            detail = None
                    st.error(detail or f"Chat request failed: {exc}")
                except requests.RequestException as exc:
                    st.error(f"Could not reach the chat service: {api_error_message(exc)}")
                else:
                    st.write(result["answer"])
                    for source in result["sources"]:
                        citation = source["document_name"]
                        if source.get("page_number") is not None:
                            citation += f", page {source['page_number']}"
                        st.caption(f"[{source['source_id']}] {citation}")
                        if source.get("source_url"):
                            st.link_button(
                                "Open source website",
                                source["source_url"],
                                key=f"latest-source-{source['source_id']}",
                            )
                    st.session_state.messages.append({
                        "role": "assistant",
                        "content": result["answer"],
                        "sources": result["sources"],
                    })

# BACKEND STATUS
st.divider()

try:
    response = requests.get(
        f"{BACKEND_URL}/health",
        timeout=3
    )
    response.raise_for_status()

    st.success("Backend connected successfully")

except requests.RequestException as exc:
    st.error(f"Backend is offline or unhealthy: {exc}")
