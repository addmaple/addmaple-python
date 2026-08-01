from __future__ import annotations

import pyarrow.ipc as ipc
import pytest

from addmaple.dataset import _encode_write_column, _infer_kind


def test_infer_kind_numeric():
    import pandas as pd

    assert _infer_kind(pd.Series([1.0, 2.0])) == "numeric"
    assert _infer_kind(pd.Series([1, 2, 3], dtype="Int64")) == "numeric"


def test_infer_kind_categorical():
    import pandas as pd

    assert _infer_kind(pd.Series(["a", "b"], dtype="category")) == "categorical"
    assert _infer_kind(pd.Series([True, False])) == "categorical"


def test_infer_kind_multi_select():
    import pandas as pd

    assert _infer_kind(pd.Series([["a"], ["b", "c"], None], dtype=object)) == "multi_select"


def test_infer_kind_text():
    import pandas as pd

    assert _infer_kind(pd.Series(["hello", "world"], dtype=object)) == "text"


def test_encode_write_column_roundtrip():
    import pandas as pd

    series = pd.Series([1.5, 2.5, None], dtype="float64")
    body = _encode_write_column(series, row_count=3)
    table = ipc.open_stream(body).read_all()

    assert table.column_names == ["__row_index", "value"]
    assert table.num_rows == 3
    assert table.column("__row_index").to_pylist() == [0, 1, 2]
    assert table.column("value").to_pylist() == [1.5, 2.5, None]


def test_encode_write_column_rejects_short_series_with_full_row_count():
    import pandas as pd

    series = pd.Series([1.0, 2.0])
    body = _encode_write_column(series, row_count=2)
    table = ipc.open_stream(body).read_all()
    assert table.num_rows == 2


@pytest.mark.parametrize(
    "values,expected_kind",
    [
        ([1, 2, 3], "numeric"),
        (["a", "b"], "text"),
    ],
)
def test_infer_kind_from_list_like_values(values, expected_kind):
    import pandas as pd

    assert _infer_kind(pd.Series(values)) == expected_kind
