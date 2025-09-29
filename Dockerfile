FROM python:3.11-slim

# Create app directory
WORKDIR /app

# Copy requirements and install
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

# Copy app
COPY . /app

# Expose Streamlit port and Prometheus metrics port
EXPOSE 8501 8000

# Streamlit runs on 8501 by default; metrics server started by the app on 8000
CMD ["streamlit", "run", "main.py", "--server.port=8501", "--server.headless=true"]
