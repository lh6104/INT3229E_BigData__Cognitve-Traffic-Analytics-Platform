"""Static notebook quality check for environments without Jupyter."""

from __future__ import annotations

import argparse
import ast
import json
from pathlib import Path


REQUIRED_SECTIONS = [
    "1. Project setup",
    "2. Load dataset",
    "3. Inspect data",
    "4. Feature selection",
    "5. Train/validation split",
    "6. Baseline model",
    "7. LightGBM model training",
    "8. Evaluation metrics",
    "9. Feature importance",
    "10. Error analysis",
    "11. Save model artifact",
    "12. Save model manifest",
    "13. Optional MLflow logging",
    "14. Conclusion and limitations",
]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("notebook", default="notebooks/01_train_traffic_forecasting_model.ipynb")
    args = parser.parse_args()
    path = Path(args.notebook)
    notebook = json.loads(path.read_text(encoding="utf-8"))
    cells = notebook.get("cells", [])
    markdown = "\n".join("".join(cell.get("source", [])) for cell in cells if cell.get("cell_type") == "markdown")
    missing = [section for section in REQUIRED_SECTIONS if section not in markdown]
    if missing:
        raise SystemExit(f"Missing notebook sections: {missing}")

    source_text = "\n".join("".join(cell.get("source", [])) for cell in cells)
    forbidden = ["/home/longha", "/home/phuc", "TOMTOM_API_KEY", "OPENWEATHER_API_KEY", "NEO4J_PASSWORD"]
    found = [token for token in forbidden if token in source_text]
    if found:
        raise SystemExit(f"Forbidden local path/secret-like token in notebook: {found}")

    for index, cell in enumerate(cells):
        if cell.get("cell_type") != "code":
            continue
        source = "".join(cell.get("source", []))
        try:
            ast.parse(source)
        except SyntaxError as exc:
            raise SystemExit(f"Syntax error in code cell {index}: {exc}") from exc
    print(f"PASS notebook static check path={path} cells={len(cells)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
