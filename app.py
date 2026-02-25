import os

# Disable telemetry & opentelemetry
os.environ["CREWAI_TELEMETRY_ENABLED"] = "false"
os.environ["OTEL_SDK_DISABLED"] = "true"
os.environ["OPENTELEMETRY_SDK_DISABLED"] = "true"

import streamlit as st
import pdfplumber
from qa_engine import QACrew, export_excel, normalize_list, safe_json
from dotenv import load_dotenv

# === DEBUG: Check Gemini API key ===
try:
    import google.generativeai as genai
    st.sidebar.success(f"✅ Google Generative AI loaded")
    
    api_key = os.getenv("GEMINI_API_KEY") or st.secrets.get("GEMINI_API_KEY", None)
    if api_key:
        st.sidebar.success(f"✅ Gemini API key found (length: {len(api_key)})")
        st.sidebar.info(f"✅ API key starts with: {api_key[:10]}...")
        
        # Test the API key directly
        try:
            genai.configure(api_key=api_key)
            # List models to test authentication
            models = genai.list_models()
            st.sidebar.success("✅ Gemini connection successful!")
        except Exception as e:
            st.sidebar.error(f"❌ Gemini connection failed: {str(e)}")
    else:
        st.sidebar.error("❌ Gemini API key missing")
except ImportError as e:
    st.sidebar.error(f"❌ Google Generative AI import failed: {str(e)}")
except Exception as e:
    st.sidebar.error(f"❌ Error: {str(e)}")
# =============================

# Load .env for local
load_dotenv()

# ---- API KEY LOADER (env OR streamlit secrets) ----
api_key = os.getenv("GEMINI_API_KEY") or st.secrets.get("GEMINI_API_KEY", None)

if not api_key:
    st.error("❌ GEMINI_API_KEY not found. Add it to .env or Streamlit secrets.")
    st.info("🔑 Get your free Gemini API key from: https://aistudio.google.com/app/apikey")
    st.stop()

# Set the API key in environment for qa_engine to use
os.environ["GEMINI_API_KEY"] = api_key
# --------------------------------------------------

st.set_page_config(page_title="AI QA Generator", layout="centered")
st.title("📄 AI BRD → Test Case Generator")
st.caption("Powered by Google Gemini (Free Tier)")

# Add a sidebar with info
with st.sidebar:
    st.header("ℹ️ About")
    st.markdown("""
    This app uses **Google Gemini 1.5 Flash** (free tier) to:
    - Analyze BRD documents
    - Generate test scenarios
    - Create detailed test cases
    - Identify edge cases
    - Suggest automation candidates
    """)
    
    st.divider()
    
    if api_key:
        st.success("✅ Gemini API connected")
    else:
        st.error("❌ Gemini API not configured")

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
    
    # Show preview in an expander
    with st.expander("📄 Preview BRD Content"):
        st.text(brd_text[:2000] + ("..." if len(brd_text) > 2000 else ""))
    
    if st.button("🚀 Generate Test Cases", type="primary"):
        with st.spinner("🤖 AI agents are analyzing your BRD... (this may take a minute)"):
            try:
                crew = QACrew().qacrew()
                result = crew.kickoff(inputs={"project_name": uploaded_file.name, "brd_text": brd_text})

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
                    st.download_button(
                        "⬇️ Download QA Excel Report", 
                        f, 
                        file_name=file_name,
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                    )

                st.success("✅ Test cases generated successfully!")
                
                # Show summary
                st.info(f"📊 Generated: {len(scenarios)} scenarios, {len(tcs)} test cases, {len(edges)} edge cases")
                
            except Exception as e:
                st.error(f"❌ Error generating test cases: {str(e)}")
                st.exception(e)