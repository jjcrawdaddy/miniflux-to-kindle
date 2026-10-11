FROM python:3.13-slim AS test

WORKDIR /repo

COPY requirements.txt requirements-dev.txt ./
RUN pip install --no-cache-dir -r requirements-dev.txt

COPY app/ app/
COPY tests/ tests/

CMD ["python", "-m", "pytest", "tests/", "-v"]


FROM python:3.13-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ .

RUN useradd --system --no-create-home appuser
USER appuser

# Tolerance is 30m, not 5m: schedule.run_pending() runs the digest job
# synchronously in the same loop, and a large digest can legitimately take
# minutes. Still detects a wedged loop within ~35m vs ~24h via healthchecks.io.
HEALTHCHECK --interval=5m --timeout=10s --start-period=60s --retries=2 \
  CMD python -c "import time,sys;sys.exit(0 if time.time()-float(open('/tmp/heartbeat').read())<1800 else 1)"

CMD ["python", "main.py"]
