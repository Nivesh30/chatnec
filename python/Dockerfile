FROM python:3.12-slim

WORKDIR /app

COPY pyproject.toml ./
COPY chatnec ./chatnec

RUN pip install --no-cache-dir .[teams]

COPY examples ./examples

EXPOSE 8000

CMD ["uvicorn", "chatnec.server:app", "--host", "0.0.0.0", "--port", "8000"]
