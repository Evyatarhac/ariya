from .base import BaseAgent
from .scout import ScoutAgent
from .architect import ArchitectAgent
from .sentinel import SentinelAgent
from .forge_be import ForgeBeAgent
from .forge_fe import ForgeFeAgent
from .probe import ProbeAgent
from .guardian import GuardianAgent
from .phoenix import PhoenixAgent

ALL_AGENT_CLASSES = [
    ScoutAgent, ArchitectAgent, SentinelAgent,
    ForgeBeAgent, ForgeFeAgent, ProbeAgent,
    GuardianAgent, PhoenixAgent,
]

__all__ = ["BaseAgent", "ALL_AGENT_CLASSES"] + [c.__name__ for c in ALL_AGENT_CLASSES]
