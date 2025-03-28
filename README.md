# Usage

## Local dev server
uvicorn main:app --reload

## Public server
uvicorn main:app --reload --host 0.0.0.0

## Profiling most heavy process
poetry run pyinstrument -m pytest -k swiss
