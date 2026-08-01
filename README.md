# addmaple Python client

Use **AddMaple** for fast, interactive survey and market-research analysis in the browser — and use this library when you need the full power of Python on the same data.

The `addmaple` package gives you **programmatic access to datasets stored in AddMaple**. Pull a project into **pandas** or **Polars** (via Apache Arrow) and run models, NLP, custom scoring, or any offline workflow in your own environment. When you are done, **write new columns back**; they are **persisted on the project** and show up in the **AddMaple UI** for charts, filters, crosstabs, and sharing — no re-uploading spreadsheets.

**Typical flow:** connect → load dataset → analyze locally → `write_column()` → explore the new variables in AddMaple.

```python
import os
import addmaple

client = addmaple.connect(
    "https://addmaple.com",
    token=os.environ["ADDMAPLE_TOKEN"],
)
for project in client.list_projects():
    print(project["projectId"], project["name"])

ds = client.dataset("my-project-id")

df = ds.to_pandas()
df["score"] = df["age"] * 1.5
ds.write_column("Score", df["score"], kind="numeric")
```

Authentication uses a **product API key** (`connect(..., token=...)` or the `ADDMAPLE_TOKEN` environment variable).

## Install

```bash
pip install addmaple
pip install "addmaple[polars]"   # optional Polars support
```

Source: [github.com/addmaple/addmaple-python](https://github.com/addmaple/addmaple-python)

## API overview

| API | Description |
| --- | --- |
| `connect()` | Client for `https://addmaple.com` |
| `list_projects()` | List projects you can access |
| `dataset(project_id)` | Open a dataset handle |
| `schema` / `row_count` | Project metadata |
| `arrow()` / `to_pandas()` / `to_polars()` | Read columns for offline analysis |
| `write_column()` / `write_columns()` | Persist new variables to the project |

Learn more about AddMaple: [addmaple.com](https://addmaple.com) · [Help](https://addmaple.com/help)

## Development

From a git checkout: `pip install -e ".[dev]"`. Run tests with `pytest`.
