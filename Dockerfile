FROM python:3.12-alpine

# Install system dependencies
RUN apk add --no-cache \
    openjdk11-jre \
    && pip install --no-cache-dir \
        tabula-py \
        pandas \
        numpy

# Set Java home for tabula-py
ENV JAVA_HOME=/usr/lib/jvm/java-11-openjdk

# Create app directory
WORKDIR /srv/aftis

# Copy application files
COPY parse.py .
COPY server.py .

# Create directories
RUN mkdir -p inbox tmp

# Expose port
EXPOSE 8080