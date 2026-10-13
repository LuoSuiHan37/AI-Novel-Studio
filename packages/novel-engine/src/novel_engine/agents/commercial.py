from novel_engine.agents.base import BaseAgent
from novel_engine.agents.contracts import CommercialReviewInput, CommercialReviewOutput


class CommercialReviewAgent(BaseAgent[CommercialReviewInput, CommercialReviewOutput]):
    name = "commercial_review"
    prompt_file = "agents/commercial_review.yaml"
    input_model = CommercialReviewInput
    output_model = CommercialReviewOutput
