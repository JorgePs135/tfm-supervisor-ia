FROM python:3.11-slim

# Instala Git (necesario para los comandos nativos) y la librería de Gemini
RUN apt-get update && apt-get install -y git && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir google-genai

# IMPORTANTE: No copiamos main.py aquí para evitar que se quede congelado en el caché.
# Le decimos a Docker que ejecute el main.py que GitHub monta en vivo en el workspace.
ENTRYPOINT ["python", "/github/workspace/main.py"]