import os
import redis
import json
import logging
import requests
from minio import Minio
import time
import subprocess
import psycopg2
from psycopg2 import sql


# PostgreSQL connection settings
SQL_DATABASE = {
    'host': os.getenv('POSTGRES_HOST', 'localhost'),
    'dbname': os.getenv('POSTGRES_DB', 'yourdatabase'),
    'user': os.getenv('POSTGRES_USER', 'postgres'),
    'password': os.getenv('POSTGRES_PASSWORD', 'yourpassword'),
    'port': 5432 
}

def sql_db_connection():
    """Creates and returns a new database connection."""
    try:
        conn = psycopg2.connect(**SQL_DATABASE)
        return conn
    except psycopg2.Error as e:
        raise Exception(f"Failed to connect to the database: {e}")

# Function to connect to the PostgreSQL database
def get_sql_db_connection():
    conn = psycopg2.connect(**SQL_DATABASE)
    return conn
portgres_client = get_sql_db_connection()


# Configuration
REDIS_HOST = os.getenv('REDIS_HOST', 'localhost')

# MinIO configuration
MINIO_HOST = os.getenv("MINIO_HOST", "localhost:9000")
MINIO_ACCESS_KEY = os.getenv("MINIO_ACCESS_KEY", "rootuser")
MINIO_SECRET_KEY = os.getenv("MINIO_SECRET_KEY", "rootpass123")
REDIS_KEY_WORKER = 'toWorker'
REDIS_KEY_LOG = 'logging'

# Setup Redis and Minio clients
def create_minio_client():
    while True:
        try:
            minio_client = Minio(
                MINIO_HOST,
                access_key=MINIO_ACCESS_KEY,
                secret_key=MINIO_SECRET_KEY,
                secure=False
            )
            # Try to list buckets as a way to test the connection
            minio_client.list_buckets()
            print("Connected to MinIO.")
            return minio_client
        except Exception as e:
            print(f"Connection to MinIO failed: {e}. Retrying in 5 seconds...")
            time.sleep(5)  # Wait 5 seconds before retrying

# Create the MinIO client
minio_client = create_minio_client()

def create_redis_client():
    while True:
        try:
            redis_client = redis.Redis(host=REDIS_HOST, port=6379, db=0)
            # Test the connection to ensure it's available
            redis_client.ping()
            print("Connected to Redis.")
            return redis_client
        except redis.exceptions.ConnectionError as e:
            print(f"Connection failed: {e}. Retrying in 5 seconds...")
            time.sleep(5)  # Wait 5 seconds before retrying

# Create the Redis client
redis_client = create_redis_client()

# Log setup
logging.basicConfig(level=logging.INFO)

def log_info(message):
    redis_client.rpush(REDIS_KEY_LOG, message)

def download_image(image_key):
    filename = f"./images/input/{image_key}.jpg"
    minio_client.fget_object(image_key, f"{image_key}.jpg" , filename)
    return filename

def process_image_with_alpr(image_file):
    try:
        command = ["alpr", "-c", "us", image_file]
        result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        if result.returncode != 0:
            raise Exception(f"ALPR command failed: {result.stderr}")
        return result.stdout
    except Exception as e:
        raise Exception(f"Error processing image with ALPR: {e}")

def upload_results_to_minio(image_key, results):
    result_file = f"./output/{image_key}.json"

    os.makedirs(os.path.dirname(result_file), exist_ok=True)

    # Save the results to a JSON file
    with open(result_file, "w") as f:
        json.dump(results, f, indent=4)

    update_query = """
        UPDATE transactions
        SET license_plate = %s, results = %s
        WHERE filename = %s;
    """
    print(results)
    
    # Extract the output string
    alpr_output = results.get('alpr_output', 'none')
    
    # Split into lines
    lines = alpr_output.split('\n')

    # Skip the first line (it contains metadata, not results)
    result_lines = lines[1:]
    results_lst = []
    if alpr_output != 'none':
        # Parse each result line
        for line in result_lines:
            if line.strip():  # Skip empty lines
                # Remove the leading dash and split by tab and confidence
                plate, confidence = line.strip('- ').split('\t confidence: ')
                results_lst.append({
                    'plate': plate.strip(),
                    'confidence': float(confidence.strip())
                })
        print("=========================")
        print(results_lst[0]['plate'], str(results_lst), image_key)
        
        # Serialize results_lst as JSON before passing it to SQL
        results_json = json.dumps(results_lst)

        # Execute the update query
        try:
            with sql_db_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute(update_query, (
                        results_lst[0]['plate'], results_json, f"{image_key}.jpg"
                    ))
                    # Commit the transaction
                    conn.commit()

                    # Fetch the updated transaction id (if any)
                    # transaction_id = cursor.fetchone()
                    print(f"Updated transaction for {image_key}")
        except Exception as e:
            print(f"Error updating database: {e}")
    
    # Upload the results to MinIO
    minio_client.fput_object(image_key, f"{image_key}.json", result_file)
    print(f"Uploaded results for {image_key} to MinIO.")
    
def main():
    while True:
        try:
            task = redis_client.blpop(REDIS_KEY_WORKER, timeout=3)
            print("Received task:", task)
            
            # Initialize image_key to avoid unbound variable issue
            image_key = None
            if task:
                try:
                    image_key = task[1].decode('utf-8')
                    print("Parsed message:", image_key)
                    
                    # Step 1: Download the image from MinIO
                    image_file = download_image(image_key)
                    log_info(f"Downloaded image {image_key} for processing.")
                    
                    # Step 2: Process the image with OpenALPR (via command-line)
                    alpr_results = process_image_with_alpr(image_file)
                    log_info(f"Processed image {image_key} using ALPR.")
                    print(alpr_results)
                    
                    # Convert results to JSON-like format for consistency
                    results = {"alpr_output": alpr_results}
                    
                    # Step 3: Save and upload the results to MinIO
                    upload_results_to_minio(image_key, results)
                    
                except json.JSONDecodeError as e:
                    logging.error(f"JSON decode error: {e}. Task content: {task[1]}")
                    log_info(f"Failed to parse JSON for task: {task[1]}")
                    
                except Exception as e:
                    logging.error(f"Failed to process task: {e}")
                    if image_key:
                        log_info(f"Failed to process task for image {image_key}")
                    else:
                        log_info("Failed to process task due to missing image_key")
        except Exception as e:
            print(e)
        time.sleep(5)

if __name__ == "__main__":
    main()
