from app.core.config import Settings


def test_settings_defaults():
    # Ignore .env so we assert true defaults
    s = Settings(_env_file=None)
    assert s.ENV in {"development", "staging", "production", "test"}
    assert s.PORT == 8000
    assert s.IMAGE_CACHE_DIR == "img-cache"


def test_settings_env_overrides(monkeypatch, tmp_path):
    # Prove overrides work even when .env is ignored
    monkeypatch.setenv("PORT", "9000")
    monkeypatch.setenv("LOG_LEVEL", "DEBUG")
    s = Settings(_env_file=None)
    assert s.PORT == 9000
    assert s.LOG_LEVEL == "DEBUG"
