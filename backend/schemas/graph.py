from pydantic import BaseModel
from typing import Literal


class BuildRequest(BaseModel):
    vk_id: str
    mode: Literal["friends", "friends_of_friends"]


class GraphStats(BaseModel):
    nodes: int
    edges: int
    most_connected: str
    most_connected_degree: int


class BuildResponse(BaseModel):
    session_id: str
    plotly_json: str
    stats: GraphStats
