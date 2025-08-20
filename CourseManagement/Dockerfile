FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    libmagic1 gcc build-essential && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.in .
RUN pip install --upgrade pip && pip install -r requirements.in

COPY . .

EXPOSE 8000

CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]