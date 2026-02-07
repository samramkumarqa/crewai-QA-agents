from typing import List
from crewai import Agent, Crew, Process, Task, LLM
from crewai.project import CrewBase, agent, crew, task
from dotenv import load_dotenv
from openpyxl import Workbook
from datetime import datetime
import json, re

load_dotenv()

llm = LLM(
    model="together_ai/meta-llama/Meta-Llama-3.1-8B-Instruct-Turbo",
    temperature=0.3,
    max_tokens=1500,
    request_timeout=30
)

# ---------- Normalise Edge ----------
def normalize_edge(e):
    if isinstance(e, dict):
        return str(e.get("description", e))
    return str(e)

# ---------- Normalise Steps ----------
def normalize_steps(raw_steps):
    if not raw_steps:
        return ""

    # If list
    if isinstance(raw_steps, list):
        cleaned = []
        for s in raw_steps:
            if isinstance(s, dict):
                cleaned.append(str(s.get("step", s)))
            else:
                cleaned.append(str(s))
        return "\n".join(cleaned)

    # If dict
    if isinstance(raw_steps, dict):
        return str(raw_steps.get("step", raw_steps))

    # If string → try to split on sentence boundaries
    if isinstance(raw_steps, str):
        # split before "User", "System", "Admin"
        parts = re.split(r'(?=(User|System|Administrator))', raw_steps)
        merged = []
        buffer = ""
        for p in parts:
            if p in ["User", "System", "Administrator"]:
                if buffer:
                    merged.append(buffer.strip())
                buffer = p
            else:
                buffer += p
        if buffer:
            merged.append(buffer.strip())

        # If split worked
        if len(merged) > 1:
            return "\n".join(merged)

        return raw_steps

    return str(raw_steps)    

# ---------- Normalise List ----------
def normalize_list(data):
    if not data:
        return []
    if isinstance(data, (dict, str)):
        return [data]
    if isinstance(data, list):
        return data
    return [str(data)]

# ---------- JSON Safe ----------
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

# ---------- Excel Export ----------
def export_excel(brd, scenarios, tcs, edges, auto):

    brd = normalize_list(brd)
    scenarios = normalize_list(scenarios)
    tcs = normalize_list(tcs)
    edges = normalize_list(edges)
    auto = normalize_list(auto)

    wb = Workbook()

    # --- BRD ---
    ws1 = wb.active
    ws1.title = "BRD Analysis"
    ws1.append(["Module", "Description"])
    for r in brd:
        if isinstance(r, dict):
            ws1.append([r.get("module",""), r.get("description","")])
        else:
            ws1.append(["", str(r)])

    # --- Scenarios ---
    ws2 = wb.create_sheet("Test Scenarios")
    ws2.append(["ID", "Description"])
    for s in scenarios:
        if isinstance(s, dict):
            ws2.append([s.get("id",""), s.get("description","")])
        else:
            ws2.append(["", str(s)])

    # --- Detailed Test Cases ---
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

    # --- Edge Cases ---
    ws4 = wb.create_sheet("Edge Cases")
    ws4.append(["Edge Case"])
    for e in edges:
        ws4.append([normalize_edge(e)])

    # --- Automation ---
    ws5 = wb.create_sheet("Automation Candidates")
    ws5.append(["ID", "Reason"])
    for a in auto:
        if isinstance(a, dict):
            ws5.append([a.get("id",""), a.get("reason","")])
        else:
            ws5.append(["", str(a)])

    name = f"QA_Report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    wb.save(name)
    print("✅ Excel generated:", name)

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
        return Crew(
            agents=self.agents,
            tasks=self.tasks,
            process=Process.sequential,
            verbose=True
        )

# ---------- Run ----------
if __name__ == "__main__":
    inputs = {
        "project_name": "Banking Login Module",
        "brd_text": """
        User logs in using username and password.
        System locks account after 3 failures.
        Forgot password sends reset link.
        """
    }

    crew = QACrew().qacrew()
    crew.kickoff(inputs=inputs)

    brd = scenarios = tcs = edges = auto = []

    for t in crew.tasks:
        raw = t.output.raw if hasattr(t.output, "raw") else ""
        if t.name == "brd_analysis":
            brd = safe_json(raw)
        elif t.name == "test_scenarios":
            scenarios = safe_json(raw)
        elif t.name == "detailed_testcases":
            tcs = safe_json(raw)
        elif t.name == "edge_case_review":
            edges = safe_json(raw)
        elif t.name == "automation_candidates":
            auto = safe_json(raw)

    export_excel(brd, scenarios, tcs, edges, auto)
