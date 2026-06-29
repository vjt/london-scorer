from london_scorer import config


def test_load_config_reads_yaml(tmp_path):
    p = tmp_path / "z.yaml"
    p.write_text("destination: King's Cross\ncommute_threshold_min: 45\n")
    cfg = config.load_config(p)
    assert cfg["destination"] == "King's Cross"
    assert cfg["commute_threshold_min"] == 45


def test_load_env_parses_and_skips_comments(tmp_path):
    p = tmp_path / ".env"
    p.write_text("# comment\nTFL_APP_KEY=abc\n\nEPC_BEARER_TOKEN=xyz\n")
    env = config.load_env(p)
    assert env["TFL_APP_KEY"] == "abc"
    assert env["EPC_BEARER_TOKEN"] == "xyz"
