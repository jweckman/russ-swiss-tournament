# Usage

## Local dev server
uv run uvicorn main:app --reload

## Public server
uv run uvicorn main:app --reload --host 0.0.0.0

## Profiling most heavy process
uv run pyinstrument -m pytest -k swiss
