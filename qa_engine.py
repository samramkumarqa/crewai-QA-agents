# qa_engine.py
from crewai import Agent, Crew, Process, Task, LLM
from crewai.project import CrewBase, agent, crew, task
from dotenv import load_dotenv
from openpyxl import Workbook
from datetime import datetime
import json, re
import ast
import os

load_dotenv()

llm = LLM(
    model="together/meta-llama/Meta-Llama-3.1-8B-Instruct-Turbo",
    api_key=os.getenv("TOGETHER_API_KEY"),
    temperature=0.0,
    is_litellm=True   # 🔥 force LiteLLM mode
)


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

def normalize_steps(raw_steps):
    if not raw_steps:
        return ""
    if isinstance(raw_steps, list):
        return "\n".join(str(s.get("step", s)) if isinstance(s, dict) else str(s) for s in raw_steps)
    if isinstance(raw_steps, dict):
        return str(raw_steps.get("step", raw_steps))
    if isinstance(raw_steps, str):
        parts = re.split(r'(?=(User|System|Administrator))', raw_steps)
        merged, buf = [], ""
        for p in parts:
            if p in ["User", "System", "Administrator"]:
                if buf: merged.append(buf.strip())
                buf = p
            else:
                buf += p
        if buf: merged.append(buf.strip())
        return "\n".join(merged) if len(merged) > 1 else raw_steps
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
