from pathlib import Path

import pytest

from vouch_backend import openapi


def test_openapi_generate_then_check_is_current_and_nonmutating(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    destination = tmp_path / "openapi.json"
    monkeypatch.setattr(openapi, "DESTINATION", destination)
    monkeypatch.setattr(openapi, "render_schema", lambda: '{"synthetic":"schema"}\n')
    openapi.main([])
    before = destination.read_bytes()

    def unexpected_write(*args: object, **kwargs: object) -> None:
        pytest.fail("OpenAPI --check must never write the schema.")

    monkeypatch.setattr(Path, "write_text", unexpected_write)
    openapi.main(["--check"])
    assert destination.read_bytes() == before


@pytest.mark.parametrize("present", [False, True], ids=["missing", "stale"])
def test_openapi_check_fails_clearly_without_repairing_artifacts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str],
    present: bool,
) -> None:
    destination = tmp_path / "openapi.json"
    monkeypatch.setattr(openapi, "DESTINATION", destination)
    monkeypatch.setattr(openapi, "render_schema", lambda: '{"current":true}\n')
    if present:
        destination.write_text("preserve stale artifact", encoding="utf-8")
    with pytest.raises(SystemExit) as failure:
        openapi.main(["--check"])
    assert failure.value.code == 1
    assert ("stale" if present else "missing") in capsys.readouterr().err
    if present:
        assert destination.read_text(encoding="utf-8") == "preserve stale artifact"
    else:
        assert not destination.exists()


def test_rendering_openapi_does_not_start_database_lifespan(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def unexpected_database_setup() -> None:
        pytest.fail("Schema generation must not start the database lifespan.")

    monkeypatch.setattr(openapi.app.state.database, "create_all", unexpected_database_setup)
    rendered = openapi.render_schema()
    assert '"openapi": "3.1.0"' in rendered
