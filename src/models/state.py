import operator
from typing import Annotated, Sequence

from langchain_core.messages import BaseMessage
from typing_extensions import TypedDict


class AgentState(TypedDict):
    """
    L'état partagé par nos agents pour l'architecture HorRAGor v3.0.
    Chaque agent lira et écrira dans cette structure.
    """

    # L'opérateur add permet d'accumuler les messages (historique) sans les écraser
    messages: Annotated[Sequence[BaseMessage], operator.add]

    # Nous pourrons ajouter ici d'autres clés plus tard (ex: 'verdict' pour un Juge)
