FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
RUN pip install --no-cache-dir "numpy>=1.26,<3" "requests>=2.31,<3"
# Only a pure signal module and the simulation are present. No real clients,
# Guardian process, message sender, planner application or executor is copied.
COPY guardian_signals.py /app/guardian_signals.py
COPY igod_paper /app/igod_paper
EXPOSE 8080
CMD ["python", "-m", "igod_paper", "--directory", "/paper-data", "--serve"]
