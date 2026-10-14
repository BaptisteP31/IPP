FROM python:3.13-slim

WORKDIR /app

# The app runs as a host UID with no home directory; gunicorn needs a writable one.
ENV HOME=/tmp

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY main.py tokens.py entrypoint.sh ./

# Fixes ownership of the mounts as root, then drops to PUID:PGID.
ENTRYPOINT ["/app/entrypoint.sh"]
# One worker only: the refresh thread must run exactly once.
CMD ["gunicorn", "--workers", "1", "--threads", "4", "--bind", "0.0.0.0:5000", "main:app"]
