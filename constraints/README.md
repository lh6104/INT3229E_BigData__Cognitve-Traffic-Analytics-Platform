# Python 3.11 constraints

`python311.txt` records the complete resolved development environment used by CI
and local Docker API/streaming builds. It deliberately includes FastAPI and its
resolved Starlette version together, rather than independently narrowing
Starlette in the project metadata. Both HTTPX and HTTPX2 remain development
dependencies to support old and new Starlette TestClient transports.

Install from the repository root:

```sh
python -m pip install -c constraints/python311.txt -e '.[dev]'
python -m pip check
```

A constraint does not install dependencies by itself. Runtime extras install only
their own requirements, constrained to these tested versions. MLflow and the
existing ML stack have not been upgraded for the rubric work. Optional Airflow
and PyFlink have their own incompatible environments and do not use this file.

To update intentionally, create a fresh Python 3.11 environment, install the
requested targeted dependency change, run `pip check`, backend tests, real
PostgreSQL integration and Compose smoke, then regenerate with
`python -m pip freeze --exclude-editable`. Do not freeze a shared Conda environment.
The supported minimum FastAPI version is verified separately with a small
TestClient smoke, outside this primary resolved stack.
