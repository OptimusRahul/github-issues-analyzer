from pathlib import Path

import yaml

ACTION = yaml.safe_load((Path(__file__).parents[2] / "action.yml").read_text())


def test_action_declares_its_inputs():
    assert set(ACTION["inputs"]) == {"command", "issue-number", "github-token", "config", "llm-api-key"}
    assert ACTION["runs"]["using"] == "composite"


def test_run_step_passes_inputs_through_env_not_into_the_script():
    run_steps = [s for s in ACTION["runs"]["steps"] if "run" in s]
    assert run_steps
    for step in run_steps:
        assert "${{" not in step["run"]  # expressions in scripts allow shell injection from issue data
        assert step["shell"] == "bash"


def test_index_and_model_cache_use_the_same_paths_for_restore_and_save():
    caches = [s["with"] for s in ACTION["runs"]["steps"] if s.get("uses", "").startswith("actions/cache/")]
    assert len(caches) == 2 and caches[0]["path"] == caches[1]["path"]
