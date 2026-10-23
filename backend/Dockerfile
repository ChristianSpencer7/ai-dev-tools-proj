FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app
COPY pyproject.toml manage.py ./
COPY stepboard ./stepboard
COPY leaderboard ./leaderboard
RUN pip install . && rm -rf build *.egg-info  # leftovers from building the package

# The admin's and DRF's CSS and JavaScript, collected once at build time for WhiteNoise to serve.
# collectstatic needs no database or real secret; this key exists only during this step.
RUN DJANGO_DEBUG=0 DJANGO_SECRET_KEY=collectstatic-build-only python manage.py collectstatic --noinput

# Run as an unprivileged user, so a bug in the app can't change the container's system files.
RUN useradd --create-home --uid 1000 app
USER app

EXPOSE 8000
# Apply migrations, load demo data (does nothing if it's already there), then serve with gunicorn.
# exec hands gunicorn the process, so `docker compose stop` shuts it down cleanly.
CMD ["sh", "-c", "python manage.py migrate --noinput && python manage.py seed_demo && exec gunicorn stepboard.wsgi --bind 0.0.0.0:8000 --workers 2 --access-logfile -"]
