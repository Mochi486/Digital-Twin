FROM python:3.11-slim

WORKDIR /app

COPY simulator.py .

CMD ["python", "simulator.py"]