from app.schemas.ai import PromptResponse


class AIService:
    """Service IA placeholder. Remplacer par ton provider LLM (OpenAI, Azure, etc.)."""

    def run_prompt(self, prompt: str) -> PromptResponse:
        simulated_answer = (
            "[Simulation IA] Requete recue: "
            f"{prompt[:140]}"
        )
        return PromptResponse(answer=simulated_answer, model="mock-model-v1")


ai_service = AIService()
