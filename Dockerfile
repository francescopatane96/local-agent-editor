FROM python:3.12-slim
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=/app DATA_DIR=/app/data
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app ./app
COPY dashboard ./dashboard
COPY config ./config
RUN useradd --uid 10001 --create-home observatory && mkdir -p /app/data && chown observatory:observatory /app/data
USER observatory
EXPOSE 8501
CMD ["streamlit", "run", "dashboard/home.py", "--server.address=0.0.0.0", "--browser.gatherUsageStats=false"]
