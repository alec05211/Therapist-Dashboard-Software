FROM python:3.12-slim

WORKDIR /app
ENV PYTHONUNBUFFERED=1

COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt \
    && python -c "from urllib.request import urlretrieve; urlretrieve('https://truststore.pki.rds.amazonaws.com/global/global-bundle.pem', '/app/rds-ca-bundle.pem')" \
    && useradd --system --uid 10001 appuser \
    && mkdir /app/recordings \
    && chown -R appuser:appuser /app

COPY database /app/database
COPY server.py index.html synthetic_conversation.json /app/

USER appuser
EXPOSE 8000

CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers"]
