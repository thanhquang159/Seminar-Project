import asyncio

import pytest

from scripts.backfill_demo_poi_localizations import backfill


class FakeResult:
    def __init__(self, rows=()):
        self.rows = list(rows)

    def scalars(self):
        return self

    def all(self):
        return self.rows


class FakeSession:
    def __init__(self, target_ids, inserted_languages, draft_ids=()):
        self.target_ids = list(target_ids)
        self.draft_ids = list(draft_ids)
        self.inserted_languages = inserted_languages
        self.statements = []
        self.committed = False

    async def execute(self, statement, params=None):
        sql = str(statement)
        self.statements.append((sql, params or {}))
        if "FROM pois" in sql:
            ids = (
                self.target_ids
                if "publication_status = 'published'" in sql
                else self.draft_ids
            )
            return FakeResult(ids)
        if "INSERT INTO poi_localizations" in sql:
            return FakeResult((language,) for language in self.inserted_languages)
        return FakeResult()

    async def commit(self):
        self.committed = True


def test_backfill_inserts_missing_translations_and_invalidates_poi_sync():
    poi_id = "poi-id"
    session = FakeSession(
        [poi_id],
        ["en", "zh", "ja", "ko"],
        draft_ids=["draft-id"],
    )

    languages_added, draft_deactivated = asyncio.run(backfill(session))

    assert languages_added == ["en", "zh", "ja", "ko"]
    assert draft_deactivated
    localization_sql, params = session.statements[1]
    assert "ON CONFLICT (poi_id, language_code) DO NOTHING" in localization_sql
    assert params["en_name"] == "Khanh Hoi Bakery (Demo)"
    assert params["zh_name"] == "庆会面包店（演示）"
    assert "UPDATE pois SET updated_at = now()" in session.statements[2][0]
    assert session.statements[2][1] == {"poi_id": poi_id}
    assert "SET is_active = FALSE" in session.statements[4][0]
    assert session.statements[4][1] == {"poi_id": "draft-id"}
    assert session.committed


def test_backfill_is_idempotent_when_translations_already_exist():
    session = FakeSession(["poi-id"], [])

    assert asyncio.run(backfill(session)) == ([], False)
    assert len(session.statements) == 3
    assert session.committed


def test_backfill_fails_if_source_poi_is_missing_or_ambiguous():
    for target_ids in ([], ["first", "second"]):
        session = FakeSession(target_ids, [])
        with pytest.raises(RuntimeError, match="Expected exactly one"):
            asyncio.run(backfill(session))
        assert len(session.statements) == 1
        assert not session.committed
