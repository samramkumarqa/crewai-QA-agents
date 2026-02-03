from typing import List
from crewai import Agent, Crew, Process, Task, LLM
from crewai.project import CrewBase, agent, crew, task
from crewai_tools import DirectoryReadTool, FileWriterTool, FileReadTool
from dotenv import load_dotenv
from pydantic import BaseModel, Field
import os
_ = load_dotenv()

llm = LLM(
    model="together_ai/meta-llama/Meta-Llama-3.1-8B-Instruct-Turbo",
    temperature=0.5,  # slightly lower for faster response
    max_tokens=512,  # limit tokens to avoid long waits
    request_timeout=15
)

class TestCase(BaseModel):
    id: str
    scenario: str
    steps: List[str]
    expected_result: str
    test_type: str

@CrewBase
class QACrew():
    agents_config = "config/agents.yaml"
    tasks_config = "config/tasks.yaml"

    @agent
    def lead_qa(self): 
        return Agent(config=self.agents_config["lead_qa"], llm=llm)

    @agent
    def scenario_designer(self): 
        return Agent(config=self.agents_config["scenario_designer"], llm=llm)

    @agent
    def testcase_writer(self): 
        return Agent(config=self.agents_config["testcase_writer"], llm=llm)

    @agent
    def qa_reviewer(self): 
        return Agent(config=self.agents_config["qa_reviewer"], llm=llm)

    @task
    def brd_analysis(self):
        return Task(config=self.tasks_config["brd_analysis"], agent=self.lead_qa())

    @task
    def test_scenarios(self):
        return Task(config=self.tasks_config["test_scenarios"], agent=self.scenario_designer())

    @task
    def detailed_testcases(self):
        return Task(config=self.tasks_config["detailed_testcases"], agent=self.testcase_writer(), output_json=TestCase)

    @task
    def edge_case_review(self):
        return Task(config=self.tasks_config["edge_case_review"], agent=self.qa_reviewer())

    @task
    def automation_candidates(self):
        return Task(config=self.tasks_config["automation_candidates"], agent=self.qa_reviewer())

    @crew
    def qacrew(self):
        return Crew(
            agents=self.agents,
            tasks=self.tasks,
            process=Process.sequential,
            verbose=True
        )

if __name__ == "__main__":
    inputs = {
        "project_name": "Banking Login Module",
        "brd_text": "User logs in with username & password. OTP after 3 failed attempts..."
    }
    crew = QACrew()
    crew.qacrew().kickoff(inputs=inputs)
