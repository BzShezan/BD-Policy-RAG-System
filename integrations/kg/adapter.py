"""Protocol-only KG interface. Does NOT change source ranking or policy winner."""
from typing import Protocol, Sequence, Mapping, Any

class KnowledgeGraphAdapter(Protocol):
    def annotate_versions(self, source_versions: Sequence[Mapping[str, Any]]) -> Mapping[str, Any]:
        """Return optional verified relationships; never select a policy winner by date alone."""
        ...

class NoOpKGAdapter:
    def annotate_versions(self, source_versions):
        return {"teammate_annotations": None, "automatic_winner_selected": False}
