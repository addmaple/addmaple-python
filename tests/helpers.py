from __future__ import annotations

import pyarrow as pa
import pyarrow.ipc as ipc


def arrow_ipc_bytes(table: pa.Table) -> bytes:
    sink = pa.BufferOutputStream()
    with ipc.new_stream(sink, table.schema) as writer:
        writer.write_table(table)
    return sink.getvalue().to_pybytes()


def sample_dataset_table() -> pa.Table:
    return pa.table(
        {
            "__row_index": pa.array([0, 1, 2], type=pa.uint32()),
            "age": pa.array([25, 30, 35], type=pa.int32()),
            "region": pa.array(["North", "South", "North"], type=pa.string()),
        }
    )
