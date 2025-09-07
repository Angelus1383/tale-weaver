from crewai import Agent, Crew, LLM, Process, Task
from crewai.project import CrewBase, agent, crew, task
from crewai.agents.agent_builder.base_agent import BaseAgent
from tale_weaver.model.storybook import Storybook
from tale_weaver.tools.custom_tool import IllustrationTool
from typing import List
import os
# If you want to run a snippet of code before or after the crew starts,
# you can use the @before_kickoff and @after_kickoff decorators
# https://docs.crewai.com/concepts/crews#example-crew-class-with-decorators

creative_model = LLM(os.getenv("CREATIVE_MODEL", "gemini/gemini-2.5-flash"), temperature=0.9, seed=23)
tool_model = LLM(os.getenv("TOOL_MODEL", "openai/gpt-4o"), temperature=0.2, seed=23)

@CrewBase
class TaleWeaver():
    """TaleWeaver crew"""

    agents: List[BaseAgent]
    tasks: List[Task]

    # Learn more about YAML configuration files here:
    # Agents: https://docs.crewai.com/concepts/agents#yaml-configuration-recommended
    # Tasks: https://docs.crewai.com/concepts/tasks#yaml-configuration-recommended
    
    # If you would like to add tools to your agents, you can learn more about it here:
    # https://docs.crewai.com/concepts/agents#agent-tools
    @agent
    def storyteller(self) -> Agent:
        return Agent(
            config=self.agents_config['storyteller'], # type: ignore[index]
            llm=creative_model
        )

    @agent
    def illustrator(self) -> Agent:
        return Agent(
            config=self.agents_config['illustrator'], # type: ignore[index]
            tools=[IllustrationTool()],
            llm=tool_model
        )

    # To learn more about structured task outputs,
    # task dependencies, and task callbacks, check out the documentation:
    # https://docs.crewai.com/concepts/tasks#overview-of-a-task
    @task
    def create_story(self) -> Task:
        return Task(
            config=self.tasks_config['create_story'], # type: ignore[index]
            output_json=Storybook
        )

    @task
    def create_illustration(self) -> Task:
        return Task(
            config=self.tasks_config['create_illustration'], # type: ignore[index]
            output_json=Storybook
        )

    @crew
    def crew(self) -> Crew:
        """Creates the TaleWeaver crew"""
        # To learn how to add knowledge sources to your crew, check out the documentation:
        # https://docs.crewai.com/concepts/knowledge#what-is-knowledge

        return Crew(
            agents=self.agents, # Automatically created by the @agent decorator
            tasks=self.tasks, # Automatically created by the @task decorator
            process=Process.sequential,
            verbose=True,
            output_log_file="logs.json",
            # process=Process.hierarchical, # In case you wanna use that instead https://docs.crewai.com/how-to/Hierarchical/
        )
