from agent.profiles import paper_leader_profile


def test_canonical_leader_profile_owns_runtime_capabilities() -> None:
    assert "subagent" in paper_leader_profile.middleware_ids
    assert "human_pack" in paper_leader_profile.capability_ids
