from __future__ import annotations

import pytest

import addmaple


def _connect(integration_config: dict[str, str]) -> addmaple.AddMapleClient:
    token = integration_config["token"] or None
    return addmaple.connect(
        integration_config["base_url"],
        token=token,
    )


@pytest.mark.integration
def test_live_schema_and_arrow_roundtrip(integration_config: dict[str, str]) -> None:
    client = _connect(integration_config)
    try:
        ds = client.dataset(integration_config["project_id"])
        schema = ds.schema
        assert schema["rowCount"] > 0

        frame = ds.to_pandas()
        assert len(frame) == schema["rowCount"]
        assert len(frame.columns) >= 1
        assert "q1" in frame.columns or len(frame.columns) >= 1
    finally:
        client.close()


@pytest.mark.integration
def test_live_write_numeric_column(integration_config: dict[str, str]) -> None:
    client = _connect(integration_config)
    try:
        ds = client.dataset(integration_config["project_id"])
        row_count = ds.row_count
        values = [float(index + 1) for index in range(row_count)]

        result = ds.write_column(
            "PyTest Score",
            values,
            kind="numeric",
            expected_last_sequence=ds.last_sequence,
        )
        assert result["columnId"]
        assert result["lastSequence"] >= 0

        schema = ds.schema
        column_ids = {column["colId"] for column in schema["columns"]}
        assert result["columnId"] in column_ids
    finally:
        client.close()
