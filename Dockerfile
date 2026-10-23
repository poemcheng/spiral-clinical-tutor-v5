FROM python:3.13-slim
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg && rm -rf /var/lib/apt/lists/*
COPY requirements.txt requirements-extended.txt ./
RUN pip install --no-cache-dir -r requirements-extended.txt
COPY backend ./backend
COPY frontend ./frontend
COPY data ./data
COPY tools/public_start.py ./tools/public_start.py
RUN useradd --uid 10001 --create-home tutor && mkdir -p /app/runtime && chown -R tutor:tutor /app
USER tutor
ENV TUTOR_HOME=/app/runtime PLATFORM_HOST=0.0.0.0 PLATFORM_PORT=8705 DISABLE_LOCAL_VOICE=1 DEPLOYMENT_MODE=public
EXPOSE 8705
HEALTHCHECK --interval=30s --start-period=30s CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8705/health',timeout=5)"
CMD ["python", "tools/public_start.py"]
