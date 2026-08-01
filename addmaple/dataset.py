from __future__ import annotations

from typing import TYPE_CHECKING, Any, Literal

import httpx
import pyarrow as pa
import pyarrow.ipc as ipc

if TYPE_CHECKING:
    import pandas as pd

    from addmaple.client import AddMapleClient

ColumnKind = Literal["numeric", "categorical", "multi_select", "text"]


def _infer_kind(series: "pd.Series") -> ColumnKind:
    import pandas as pd

    if pd.api.types.is_bool_dtype(series.dtype):
        return "categorical"
    if pd.api.types.is_numeric_dtype(series.dtype):
        return "numeric"
    if isinstance(series.dtype, pd.CategoricalDtype):
        return "categorical"
    if series.dtype == object and series.dropna().map(lambda value: isinstance(value, list)).any():
        return "multi_select"
    return "text"


def _encode_write_column(values: Any, row_count: int) -> bytes:
    import pandas as pd

    if isinstance(values, pd.Series):
        value_array = pa.array(values, type=pa.string() if values.dtype == object else None)
    else:
        value_array = pa.array(values)

    index_array = pa.array(range(row_count), type=pa.uint32())
    table = pa.table({"__row_index": index_array, "value": value_array})
    sink = pa.BufferOutputStream()
    with ipc.new_stream(sink, table.schema) as writer:
        writer.write_table(table)
    return sink.getvalue().to_pybytes()


class Dataset:
    def __init__(self, client: "AddMapleClient", project_id: str) -> None:
        self._client = client
        self.project_id = project_id
        self._schema_payload: dict[str, Any] | None = None

    def _load_schema(self) -> dict[str, Any]:
        if self._schema_payload is None:
            response = self._client._http().get(
                f"/api/projects/{self.project_id}/engine-v2/schema"
            )
            response.raise_for_status()
            self._schema_payload = response.json()
        return self._schema_payload

    @property
    def schema(self) -> dict[str, Any]:
        return self._load_schema()

    @property
    def row_count(self) -> int:
        return int(self._load_schema().get("rowCount") or 0)

    @property
    def last_sequence(self) -> int | None:
        response = self._client._http().get(
            f"/api/projects/{self.project_id}/engine-v2/schema"
        )
        response.raise_for_status()
        raw = response.headers.get("x-addmaple-last-sequence")
        return int(raw) if raw is not None else None

    def arrow(self, columns: list[str] | None = None) -> pa.Table:
        params = {}
        if columns:
            params["columns"] = ",".join(columns)
        response = self._client._http().get(
            f"/api/projects/{self.project_id}/engine-v2/dataset.arrow",
            params=params,
        )
        response.raise_for_status()
        reader = ipc.open_stream(response.content)
        return reader.read_all()

    def to_pandas(self, columns: list[str] | None = None) -> "pd.DataFrame":
        table = self.arrow(columns=columns)
        if "__row_index" in table.column_names:
            table = table.drop(["__row_index"])
        return table.to_pandas()

    def to_polars(self, columns: list[str] | None = None):
        try:
            import polars as pl
        except ImportError as error:
            raise ImportError("Install addmaple[polars] to use to_polars()") from error
        return pl.from_arrow(self.arrow(columns=columns))

    def write_column(
        self,
        name: str,
        values: Any,
        *,
        kind: ColumnKind | None = None,
        replace_column_id: str | None = None,
        expected_last_sequence: int | None = None,
    ) -> dict[str, Any]:
        import pandas as pd

        series = values if isinstance(values, pd.Series) else pd.Series(values)
        resolved_kind = kind or _infer_kind(series)
        body = _encode_write_column(series, self.row_count)
        params: dict[str, Any] = {
            "displayName": name,
            "kind": resolved_kind,
        }
        if replace_column_id:
            params["replaceColumnId"] = replace_column_id
        if expected_last_sequence is not None:
            params["expectedLastSequence"] = expected_last_sequence

        response = self._client._http().post(
            f"/api/projects/{self.project_id}/engine-v2/external-columns",
            params=params,
            content=body,
            headers={"content-type": "application/vnd.apache.arrow.stream"},
        )
        response.raise_for_status()
        payload = response.json()
        self._schema_payload = None
        return payload

    def write_columns(self, frame: "pd.DataFrame") -> list[dict[str, Any]]:
        results = []
        for column_name in frame.columns:
            results.append(self.write_column(column_name, frame[column_name]))
        return results
