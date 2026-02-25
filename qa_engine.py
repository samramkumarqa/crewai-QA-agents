# qa_engine.py
import os
os.environ["CREWAI_TELEMETRY_ENABLED"] = "false"
os.environ["OTEL_SDK_DISABLED"] = "true"
os.environ["OPENTELEMETRY_SDK_DISABLED"] = "true"

from crewai import Agent, Crew, Process, Task, LLM
from crewai.project import CrewBase, agent, crew, task
from dotenv import load_dotenv
from openpyxl import Workbook
from datetime import datetime
from openpyxl.styles import Alignment
import json, re
import ast
import os

# === FIX: Properly initialize LiteLLM before CrewAI uses it ===
import litellm
import sys

# Ensure litellm is properly configured
litellm.drop_params = True  # Set this explicitly
litellm.set_verbose = False

# Also set environment variables that LiteLLM might need
os.environ["LITELLM_LOG"] = "ERROR"  # Reduce logging

# Optional: Configure LiteLLM for Together AI specifically
litellm.together_ai = True

# Force reload of litellm if needed
import importlib
importlib.reload(litellm)
# ============================================================

load_dotenv()

llm = LLM(
    model="together_ai/meta-llama/Meta-Llama-3.1-8B-Instruct-Turbo",
    api_key=os.getenv("TOGETHER_API_KEY"),
    temperature=0.0,
    max_tokens=1500,
    request_timeout=30
)

# ... rest of your code (keep everything else the same)

# ---------- Helpers ----------
def parse_list_of_dicts(text):
    if isinstance(text, list):
        return text
    if not isinstance(text, str):
        return []

    try:
        return ast.literal_eval(text)
    except:
        return []


# ---------- Helpers ----------
def normalize_edge(e):
    if isinstance(e, dict):
        return str(e.get("description", e))
    return str(e)

def format_steps(steps):
    if isinstance(steps, list):
        return "\n".join([f"{i+1}. {s}" for i, s in enumerate(steps)])
    return str(steps)

def normalize_steps(raw_steps):
    if not raw_steps:
        return ""

    # If already list → number & line break
    if isinstance(raw_steps, list):
        return "\n".join([f"{i+1}. {s.get('step', s) if isinstance(s, dict) else s}"
                          for i, s in enumerate(raw_steps)])

    # If dict
    if isinstance(raw_steps, dict):
        return f"1. {raw_steps.get('step', raw_steps)}"

    # If string → split by common action verbs
    if isinstance(raw_steps, str):
        parts = re.split(r'(?=Enter |Click |Verify |Select |Login |Log in |Open |Submit )', raw_steps)
        parts = [p.strip() for p in parts if p.strip()]
        if len(parts) > 1:
            return "\n".join([f"{i+1}. {p}" for i, p in enumerate(parts)])
        return raw_steps

    return str(raw_steps)


def normalize_list(data):
    if not data: return []
    if isinstance(data, (dict, str)): return [data]
    if isinstance(data, list): return data
    return [str(data)]

def safe_json(text):
    try:
        return json.loads(text)
    except:
        m = re.search(r"\[.*\]", text, re.DOTALL)
        if m:
            try:
                return json.loads(m.group())
            except:
                return []
        return []

# ---------- Excel ----------
def export_excel(brd, scenarios, tcs, edges, auto):
    brd = normalize_list(brd)
    scenarios = normalize_list(scenarios)
    tcs = normalize_list(tcs)
    edges = normalize_list(edges)
    auto = normalize_list(auto)

    wb = Workbook()
    ws1 = wb.active
    ws1.title = "BRD Analysis"
    ws1.append(["Module", "Description"])
    brd_rows = []
    for r in brd:
        if isinstance(r, str) and r.strip().startswith("["):
            brd_rows.extend(parse_list_of_dicts(r))
        elif isinstance(r, dict):
            brd_rows.append(r)

    for r in brd_rows:
        ws1.append([r.get("module",""), r.get("description","")])



    ws2 = wb.create_sheet("Test Scenarios")
    ws2.append(["ID", "Description"])
    for s in scenarios:
        ws2.append([s.get("id",""), s.get("description","")]) if isinstance(s, dict) else ws2.append(["", str(s)])

    ws3 = wb.create_sheet("Detailed Test Cases")
    ws3.append(["ID", "Scenario", "Steps", "Expected Result", "Type"])
    for t in tcs:
        if isinstance(t, dict):
            ws3.append([
                t.get("id",""),
                t.get("scenario",""),
                normalize_steps(t.get("steps")),
                t.get("expected_result",""),
                t.get("test_type","")
            ])
        else:
            ws3.append(["", str(t), "", "", ""])

    ws4 = wb.create_sheet("Edge Cases")
    ws4.append(["ID", "Scenario", "Steps", "Expected Result"])

    edge_rows = []
    for e in edges:
        if isinstance(e, str) and e.strip().startswith("["):
            edge_rows.extend(parse_list_of_dicts(e))
        elif isinstance(e, dict):
            edge_rows.append(e)

    for e in edge_rows:
        ws4.append([
            e.get("id",""),
            e.get("scenario",""),
            normalize_steps(e.get("steps")),
            e.get("expected_result","")
        ])


    ws5 = wb.create_sheet("Automation Candidates")
    ws5.append(["ID", "Reason"])
    for a in auto:
        ws5.append([a.get("id",""), a.get("reason","")]) if isinstance(a, dict) else ws5.append(["", str(a)])

    for sheet in wb.worksheets:
            for row in sheet.iter_rows():
                for cell in row:
                    cell.alignment = Alignment(wrap_text=True, vertical="top")

    for ws in wb.worksheets:
        for col in ws.columns:
            max_len = 0
            col_letter = col[0].column_letter
            for cell in col:
                try:
                    max_len = max(max_len, len(str(cell.value)))
                except:
                    pass
            ws.column_dimensions[col_letter].width = min(max_len + 3, 45)


    name = f"QA_Report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"

    wb.save(name)
    return name

# ---------- Crew ----------
@CrewBase
class QACrew():
    agents_config = "config/agents.yaml"
    tasks_config = "config/tasks.yaml"

    @agent
    def lead_qa(self): return Agent(config=self.agents_config["lead_qa"], llm=llm)

    @agent
    def scenario_designer(self): return Agent(config=self.agents_config["scenario_designer"], llm=llm)

    @agent
    def testcase_writer(self): return Agent(config=self.agents_config["testcase_writer"], llm=llm)

    @agent
    def qa_reviewer(self): return Agent(config=self.agents_config["qa_reviewer"], llm=llm)

    @task
    def brd_analysis(self): return Task(config=self.tasks_config["brd_analysis"], agent=self.lead_qa())

    @task
    def test_scenarios(self): return Task(config=self.tasks_config["test_scenarios"], agent=self.scenario_designer())

    @task
    def detailed_testcases(self): return Task(config=self.tasks_config["detailed_testcases"], agent=self.testcase_writer())

    @task
    def edge_case_review(self): return Task(config=self.tasks_config["edge_case_review"], agent=self.qa_reviewer())

    @task
    def automation_candidates(self): return Task(config=self.tasks_config["automation_candidates"], agent=self.qa_reviewer())

    @crew
    def qacrew(self):
        return Crew(agents=self.agents, tasks=self.tasks, process=Process.sequential, verbose=True)
