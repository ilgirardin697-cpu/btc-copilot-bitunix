FROM python:3.12-slim-bookworm
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 PYTHONTZPATH=""
WORKDIR /app
COPY igod_killzone_price_observer/requirements.txt /app/requirements.txt
RUN python -m pip install --no-cache-dir -r /app/requirements.txt
COPY igod_killzone_price_observer /app/igod_killzone_price_observer
EXPOSE 8080
CMD ["python", "-B", "-m", "igod_killzone_price_observer"]
