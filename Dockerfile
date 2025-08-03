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
WORKDIR /srv/aftis

# Copy application files
COPY parse.py .
COPY server.py .
COPY auto-processor.py .

# Create directories
RUN mkdir -p inbox tmp failed

# Expose port
EXPOSE 8080