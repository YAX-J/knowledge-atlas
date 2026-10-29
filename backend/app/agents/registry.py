from app.agents.code_analysis.agent import CodeAnalysisAgent
from app.agents.knowledge_extraction.agent import KnowledgeExtractionAgent
from app.agents.evidence_qa.agent import EvidenceQAAgent

_agents={item.name:item for item in (CodeAnalysisAgent(),KnowledgeExtractionAgent(),EvidenceQAAgent())}


def get_agent(name):
    return _agents[name]


def available_agents():
    return tuple(_agents)
