from app.corpus import AUTHORITIES
from app.refresh import TopicProfile
from app.refresh_cli import Tier0TargetConnector


class Delegate:
    def __init__(self) -> None:
        self.robots_checked = False

    def _ensure_robots_allow_refresh(self) -> None:
        self.robots_checked = True

    def fetch(self, candidate) -> str:
        return candidate.url


def test_tier0_target_connector_emits_exact_release_pack() -> None:
    delegate = Delegate()
    connector = Tier0TargetConnector(delegate)  # type: ignore[arg-type]
    candidates = connector.discover(TopicProfile.employment_restraints(), 25)
    assert [item.citation_key for item in candidates] == [item.citation_key for item in AUTHORITIES]
    assert connector.fetch(candidates[0]) == AUTHORITIES[0].official_url
    assert delegate.robots_checked is True

