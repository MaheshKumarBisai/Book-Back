# Use an official Python runtime as a parent image
FROM python:3.9-slim

# Set the working directory in the container
WORKDIR /app

# Install system dependencies needed for psycopg2 and other potential libraries
RUN apt-get update && apt-get install -y \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy the requirements file into the container at /app
COPY requirements.txt .

# Install any needed packages specified in requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code
COPY . .

# Create the profile directory if it defaults to local filesystem
# (Ensure it exists in code or is created here)
RUN mkdir -p profile && chmod 777 profile

# Expose port 8000
EXPOSE 8000

# Define environment variable
ENV PORT=8000
ENV PYTHONPATH=/app

# Run uvicorn when the container launches
# Assuming main.py is in the root
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
