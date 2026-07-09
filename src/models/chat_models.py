from typing import List, Optional

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    user_id: str = Field(..., description="Identifiant unique de l'utilisateur")
    question: str = Field(
        ...,
        min_length=1,
        description="La question posée par l'utilisateur concernant l'univers de l'horreur",
    )


class ChatResponse(BaseModel):
    answer: str = Field(
        ..., description="La réponse générée par l'agent et validée par le Juge"
    )
    sources: List[str] = Field(
        default_factory=list,
        description="Liste des outils ou sources (ex: Wikipédia, Base SQL) utilisés pour formuler la réponse",
    )
    needs_ui_feedback: Optional[bool] = Field(
        default=False,
        description="Flag optionnel si l'agent a besoin que le front-end affiche un élément spécifique",
    )
