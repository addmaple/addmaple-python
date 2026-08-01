from __future__ import annotations

import json

import httpx
import pyarrow as pa
import pytest

import addmaple
from tests.helpers import arrow_ipc_bytes, sample_dataset_table


class MockAddMapleTransport(httpx.BaseTransport):
    def __init__(self, project_id: str) -> None:
        self.project_id = project_id
        self.post_calls: list[dict] = []

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        path = request.url.path

        if path == "/api/engine-v2/projects":
            return httpx.Response(
                200,
                json={
                    "projects": [
                        {
                            "projectId": "proj-1",
                            "name": "Demo survey",
                            "engineVersion": "v2",
                            "updatedAt": "2026-01-01T00:00:00.000Z",
                            "createdAt": "2025-12-01T00:00:00.000Z",
                        }
                    ]
                },
            )

        if path == f"/api/projects/{self.project_id}/engine-v2/schema":
            payload = {
                "projectId": self.project_id,
                "projectName": "Demo",
                "rowCount": 3,
                "columns": [
                    {"colId": "age", "displayName": "Age", "semanticType": "numeric"},
                    {"colId": "region", "displayName": "Region", "semanticType": "categorical"},
                ],
            }
            return httpx.Response(
                200,
                json=payload,
                headers={"x-addmaple-last-sequence": "7"},
            )

        if path == f"/api/projects/{self.project_id}/engine-v2/dataset.arrow":
            columns = request.url.params.get("columns")
            table = sample_dataset_table()
            if columns:
                keep = {"__row_index", *columns.split(",")}
                table = table.select([name for name in table.column_names if name in keep])
            return httpx.Response(
                200,
                content=arrow_ipc_bytes(table),
                headers={"content-type": "application/vnd.apache.arrow.stream"},
            )

        if path == f"/api/projects/{self.project_id}/engine-v2/external-columns":
            self.post_calls.append(
                {
                    "params": dict(request.url.params),
                    "content_type": request.headers.get("content-type"),
                    "body_len": len(request.content),
                }
            )
            return httpx.Response(
                200,
                json={"columnId": "score", "lastSequence": 8},
            )

        return httpx.Response(404, json={"message": f"unexpected path: {path}"})


def test_list_projects_requires_token():
    transport = MockAddMapleTransport("proj-1")
    client = addmaple.connect("http://testserver", transport=transport)
    with pytest.raises(ValueError, match="bearer token"):
        client.list_projects()


def test_list_projects():
    transport = MockAddMapleTransport("proj-1")
    client = addmaple.connect("http://testserver", token="test-token", transport=transport)

    projects = client.list_projects()

    assert len(projects) == 1
    assert projects[0]["projectId"] == "proj-1"
    assert projects[0]["name"] == "Demo survey"


def test_schema_and_row_count():
    transport = MockAddMapleTransport("proj-1")
    client = addmaple.connect("http://testserver", transport=transport)
    ds = client.dataset("proj-1")

    assert ds.row_count == 3
    assert ds.schema["projectName"] == "Demo"
    assert len(ds.schema["columns"]) == 2
    assert ds.last_sequence == 7


def test_arrow_and_to_pandas():
    transport = MockAddMapleTransport("proj-1")
    client = addmaple.connect("http://testserver", transport=transport)
    ds = client.dataset("proj-1")

    table = ds.arrow(columns=["age"])
    assert table.column_names == ["__row_index", "age"]
    assert table.num_rows == 3

    frame = ds.to_pandas(columns=["region"])
    assert list(frame.columns) == ["region"]
    assert frame["region"].tolist() == ["North", "South", "North"]


def test_write_column_posts_arrow_body():
    import pandas as pd

    transport = MockAddMapleTransport("proj-1")
    client = addmaple.connect("http://testserver", transport=transport)
    ds = client.dataset("proj-1")

    result = ds.write_column("Score", pd.Series([1.0, 2.0, 3.0]), kind="numeric")

    assert result == {"columnId": "score", "lastSequence": 8}
    assert len(transport.post_calls) == 1
    call = transport.post_calls[0]
    assert call["params"]["displayName"] == "Score"
    assert call["params"]["kind"] == "numeric"
    assert call["content_type"] == "application/vnd.apache.arrow.stream"
    assert call["body_len"] > 0


def test_write_column_invalidates_schema_cache():
    transport = MockAddMapleTransport("proj-1")
    client = addmaple.connect("http://testserver", transport=transport)
    ds = client.dataset("proj-1")

    first = ds.schema
    ds.write_column("Score", [1.0, 2.0, 3.0], kind="numeric")
    assert ds._schema_payload is None
    second = ds.schema
    assert json.dumps(first) == json.dumps(second)
