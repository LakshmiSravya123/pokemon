FROM python:3.11-slim

# Create app directory
WORKDIR /app

# Install dependencies
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

# Copy app
COPY . /app

# Prefer running as a non-root user for security
RUN useradd --create-home appuser && chown -R appuser /app
USER appuser

# Expose Streamlit port and Prometheus metrics port
EXPOSE 8501 8000

# Environment variables (should be provided at runtime, don't bake secrets into image)
ENV POKEMON_DB_USER=neondb_owner
ENV POKEMON_DB_HOST=localhost
ENV POKEMON_DB_PORT=5432
ENV POKEMON_DB_NAME=pokemon_db

# Streamlit runs on 8501 by default; metrics server started by the app on 8000
CMD ["streamlit", "run", "main.py", "--server.port=8501", "--server.headless=true"]

# Example run (secure):
# docker run -e POKEMON_DB_PASSWORD=secret -e POKEMON_DB_HOST=mydb.example --rm -p 8501:8501 myimage:latest
