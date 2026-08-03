from naviz_api.config import Settings


def test_settings_parse_comma_separated_environment_values(monkeypatch) -> None:
    monkeypatch.setenv(
        "NAVIZ_ALLOWED_ORIGINS",
        "https://naviz.app,https://preview.naviz.app",
    )
    monkeypatch.setenv("NAVIZ_GBFS_FEEDS", "https://example.test/gbfs.json")

    settings = Settings(_env_file=None)

    assert settings.allowed_origins == (
        "https://naviz.app",
        "https://preview.naviz.app",
    )
    assert settings.gbfs_feeds == ("https://example.test/gbfs.json",)
