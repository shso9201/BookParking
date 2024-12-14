FROM python:3.10-slim

# Install OpenALPR dependencies
# Install dependencies for building OpenALPR
RUN apt-get update && apt-get install -y \
    build-essential \
    make \
    git \
    libcurl4-openssl-dev \
    libjson-c-dev \
    libmicrohttpd-dev \
    libopencv-dev \
    libtesseract-dev \
    tesseract-ocr \
    && apt-get clean



# Copy your application code
COPY . /app
WORKDIR /app

# Install Python dependencies if needed
# RUN pip3 install opencv-python numpy

# Install the required Python packages
RUN pip install -r requirements.txt
RUN pip install psycopg2-binary

RUN chmod +x ./run.sh
RUN ./run.sh

# Set the entry point for your Python script
CMD ["python3", "worker-server.py"]