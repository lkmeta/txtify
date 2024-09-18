# Use an official Python runtime as a parent image
FROM python:3.10-slim

# Set the working directory in the container
WORKDIR /app

# Copy the requirements file into the container
COPY requirements.txt .

# Install any dependencies specified in requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code into the container
COPY . .

# Ensure the Python path includes the src directory
ENV PYTHONPATH=/app/src

# Expose port 5000 to the outside world
EXPOSE 5000

# Run the application
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "5000"]
