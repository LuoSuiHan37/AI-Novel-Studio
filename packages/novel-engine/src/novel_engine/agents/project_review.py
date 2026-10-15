from novel_engine.agents.base import BaseAgent
from novel_engine.agents.contracts import ProjectReviewInput, ProjectReviewOutput


class ProjectReviewAgent(BaseAgent[ProjectReviewInput, ProjectReviewOutput]):
    name = "project_independent_review"
    prompt_file = "agents/project_independent_review.yaml"
    input_model = ProjectReviewInput
    output_model = ProjectReviewOutput
