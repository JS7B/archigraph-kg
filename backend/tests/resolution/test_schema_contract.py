from app.graph.schema import _CONSTRAINTS


def test_canonical_schema_has_unique_id_and_non_unique_normalized_lookup():
    ddl = "\n".join(_CONSTRAINTS)

    assert (
        "FOR (c:CanonicalEntity) REQUIRE c.canonical_id IS UNIQUE" in ddl
    )
    assert "FOR (c:CanonicalEntity) ON (c.normalized_name)" in ddl
    assert "REQUIRE c.normalized_name IS UNIQUE" not in ddl
