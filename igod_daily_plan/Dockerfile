FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
RUN pip install --no-cache-dir "requests>=2.31,<3" "tzdata>=2025.2"
COPY igod_daily_plan /app/igod_daily_plan
EXPOSE 8080
CMD ["python","-m","igod_daily_plan.service"]
