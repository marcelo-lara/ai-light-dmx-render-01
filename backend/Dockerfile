FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY calibrate_fixture_positions.py .
COPY main.py .
COPY data/ ./data/
COPY src/ ./src/
COPY tests/ ./tests/

EXPOSE 5141
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "5141"]
