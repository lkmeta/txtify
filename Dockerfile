# Use an official Python runtime as a parent image
FROM python:3.12-slim

# Set the working directory in the container
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    ffmpeg \
    gcc \
    python3-dev \
    curl \
    --no-install-recommends && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

# Install Poetry
RUN curl -sSL https://install.python-poetry.org | python3 - && \
    ln -s /root/.local/bin/poetry /usr/local/bin/poetry

# Copy only the pyproject.toml and poetry.lock first (for better caching)
COPY pyproject.toml poetry.lock ./

# Install only main dependencies (exclude dev dependencies)
RUN poetry install --no-root --only main

# Copy the rest of the project files into the container
COPY . .

# Ensure the Python path includes the src directory
ENV PYTHONPATH=/app/src

# Add Poetry's virtual environment to the PATH
ENV PATH="/root/.local/share/pypoetry/venv/bin:$PATH"

# Preload the model to avoid loading it on the first request
# Note: Keep in mind that this will increase the image size and build time
# Choose the model you want to preload (e.g., openai/whisper-medium)
# RUN test -d /root/.cache/huggingface || poetry run python -c "from transformers import AutoModelForSpeechSeq2Seq; AutoModelForSpeechSeq2Seq.from_pretrained('openai/whisper-medium')"

# Expose port 8010
EXPOSE 8010

# Run the application
CMD ["poetry", "run", "uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8010"]