"""Sub-agent components for company organizational structure."""

from economic_agents.sub_agents.base_agent import SubAgent
from economic_agents.sub_agents.board_member import BoardMember
from economic_agents.sub_agents.executive import Executive
from economic_agents.sub_agents.individual_contributor import IndividualContributor
from economic_agents.sub_agents.subject_matter_expert import SubjectMatterExpert

__all__ = [
    "SubAgent",
    "BoardMember",
    "Executive",
    "SubjectMatterExpert",
    "IndividualContributor",
]
