FROM python:3.10-slim

WORKDIR /app

# Instala dependências de build se necessário
RUN apt-get update && apt-get install -y \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 5000

ENV FLASK_APP=app.py
ENV FLASK_ENV=production

# Executa o servidor Flask
CMD ["python", "app.py"]
