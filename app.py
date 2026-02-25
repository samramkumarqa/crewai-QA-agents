import os

# Disable telemetry & opentelemetry
os.environ["CREWAI_TELEMETRY_ENABLED"] = "false"
os.environ["OTEL_SDK_DISABLED"] = "true"
os.environ["OPENTELEMETRY_SDK_DISABLED"] = "true"

import streamlit as st
import pdfplumber
from qa_engine import QACrew, export_excel, normalize_list, safe_json
from dotenv import load_dotenv

# In app.py, around line 13-19, update to:
# === DEBUG: Check LiteLLM ===
try:
    import litellm
    st.sidebar.success(f"✅ LiteLLM loaded")
    if hasattr(litellm, 'drop_params'):
        st.sidebar.info(f"✅ drop_params = {litellm.drop_params}")
    # Check if API key is set
    import os
    api_key = os.getenv("TOGETHER_API_KEY") or st.secrets.get("TOGETHER_API_KEY", None)
    if api_key:
        st.sidebar.success(f"✅ API key found (length: {len(api_key)})")
    else:
        st.sidebar.error("❌ API key missing")
except ImportError as e:
    st.sidebar.error(f"❌ LiteLLM import failed: {str(e)}")
# =============================

# Load .env for local
load_dotenv()

# ---- API KEY LOADER (env OR streamlit secrets) ----
api_key = os.getenv("TOGETHER_API_KEY") or st.secrets.get("TOGETHER_API_KEY", None)

if not api_key:
    st.error("❌ TOGETHER_API_KEY not found. Add it to .env or Streamlit secrets.")
    st.stop()

os.environ["TOGETHER_API_KEY"] = api_key
# --------------------------------------------------

st.set_page_config(page_title="AI QA Generator", layout="centered")
st.title("📄 AI BRD → Test Case Generator")

uploaded_file = st.file_uploader("Upload BRD PDF", type=["pdf"])

def read_pdf(file):
    text = ""
    with pdfplumber.open(file) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text()
            if page_text:
                text += page_text + "\n"
    return text

if uploaded_file:
    brd_text = read_pdf(uploaded_file)
    st.text_area("Preview", brd_text[:2000], height=200)

    if st.button("🚀 Generate Test Cases"):
        with st.spinner("Running AI agents..."):
            crew = QACrew().qacrew()
            crew.kickoff(inputs={"project_name": uploaded_file.name, "brd_text": brd_text})

            brd = scenarios = tcs = edges = auto = []

            for t in crew.tasks:
                raw = t.output.raw if hasattr(t.output, "raw") else ""
                if t.name == "brd_analysis":
                    brd = normalize_list(safe_json(raw))
                elif t.name == "test_scenarios":
                    scenarios = normalize_list(safe_json(raw))
                elif t.name == "detailed_testcases":
                    tcs = normalize_list(safe_json(raw))
                elif t.name == "edge_case_review":
                    edges = normalize_list(safe_json(raw))
                elif t.name == "automation_candidates":
                    auto = normalize_list(safe_json(raw))

            file_name = export_excel(brd, scenarios, tcs, edges, auto)

            with open(file_name, "rb") as f:
                st.download_button("⬇️ Download QA Excel", f, file_name=file_name)

            st.success("✅ Done!")
