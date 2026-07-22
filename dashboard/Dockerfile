FROM python:3.11-slim
WORKDIR /app
COPY dashboard/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt
COPY dashboard /app/dashboard
COPY scripts /app/scripts
COPY data /app/data
COPY runs/germany50-selected-paths-final /app/runs/germany50-selected-paths-final
COPY runs/minimal-rl-path-control-v1 /app/runs/minimal-rl-path-control-v1
EXPOSE 8501
CMD ["streamlit", "run", "dashboard/app.py", "--server.address=0.0.0.0", "--server.headless=true", "--server.port=8501"]
