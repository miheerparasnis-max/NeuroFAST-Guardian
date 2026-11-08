FROM python:3.12-slim

RUN groupadd --system neurofast && useradd --system --gid neurofast --create-home neurofast
WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY --chown=neurofast:neurofast app ./app
RUN mkdir /data && chown neurofast:neurofast /data

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV NEUROFAST_DATABASE_PATH=/data/neurofast.db
ENV NEUROFAST_DEMO_MODE=true

USER neurofast
EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
