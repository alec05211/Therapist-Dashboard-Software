FROM python:3.12-slim

WORKDIR /app

RUN pip install --no-cache-dir "psycopg[binary]" \
    && python -c "from urllib.request import urlretrieve; urlretrieve('https://truststore.pki.rds.amazonaws.com/global/global-bundle.pem', '/app/rds-ca-bundle.pem')"

COPY database/migrate.py /app/migrate.py
COPY database/migrations /app/migrations
COPY database/migration-container/run_migration.py /app/run_migration.py

ENTRYPOINT ["python", "run_migration.py"]
