# Use an official Python image as the base
FROM python:3.10-slim

# Set the working directory
WORKDIR /app

# Copy the current directory contents into the container at /app
COPY . /app

# Install the required Python packages
RUN pip install -r requirements.txt

# Expose the port Flask runs on
EXPOSE 5000

# Command to run the Flask application
CMD ["python", "rest-server.py"]
