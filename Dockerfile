FROM python:3.12-alpine

# Install system dependencies
RUN apk add --no-cache \
    openjdk11-jre \
    postgresql-dev \
    gcc \
    musl-dev \
    && pip install --no-cache-dir \
        tabula-py \
        pandas \
        numpy \
        psycopg2-binary \
        requests \
        watchdog

# Set Java home for tabula-py
ENV JAVA_HOME=/usr/lib/jvm/java-11-openjdk

# Create app directory
WORKDIR /app

# Copy application files
COPY parse.py .
COPY server.py .
COPY auto-processor.py .
COPY migrations.sql .

# Create data directories (mounted under /srv/aftis at runtime)
RUN mkdir -p /srv/aftis/inbox /srv/aftis/tmp /srv/aftis/failed /srv/aftis/uploads

# Expose port
EXPOSE 8080