import streamlit as st
import pdfplumber
import os
from qa_engine import QACrew, export_excel, normalize_list, safe_json

os.environ["TOGETHER_API_KEY"] = st.secrets["TOGETHER_API_KEY"]
st.set_page_config(page_title="AI QA Generator", layout="centered")
st.title("📄 AI BRD → Test Case Generator")

uploaded_file = st.file_uploader("Upload BRD PDF", type=["pdf"])

def read_pdf(file):
    text = ""
    with pdfplumber.open(file) as pdf:
        for page in pdf.pages:
            text += page.extract_text() + "\n"
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
                if t.name == "brd_analysis": brd = normalize_list(safe_json(raw))
                elif t.name == "test_scenarios": scenarios = normalize_list(safe_json(raw))
                elif t.name == "detailed_testcases": tcs = normalize_list(safe_json(raw))
                elif t.name == "edge_case_review": edges = normalize_list(safe_json(raw))
                elif t.name == "automation_candidates": auto = normalize_list(safe_json(raw))

            file_name = export_excel(brd, scenarios, tcs, edges, auto)

            with open(file_name, "rb") as f:
                st.download_button("⬇️ Download QA Excel", f, file_name=file_name)

            st.success("Done!")
