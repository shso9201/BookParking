from flask import Flask, render_template, request, jsonify, redirect, url_for
import psycopg2
from psycopg2 import sql
import hashlib
import os
import time
from datetime import datetime
from datetime import date, time, datetime
from minio import Minio
from minio.error import S3Error
import logging
import jsonpickle
import io
import redis
import base64
import re
from flask_cors import CORS  # Import CORS

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 100 * 1024 * 1024  # 100 MB limit
# Enable logging
logging.basicConfig(level=logging.DEBUG)
# Enable CORS for all routes
CORS(app)
CORS(app, origins=["http://localhost:3000"])  # Replace with your frontend origin


# Database connection configuration (using SQL_DATABASE from previous config)
# SQL_DATABASE = {
#     'dbname': 'yourdatabase',      # replace with your database name
#     'user': 'postgres',            # replace with your PostgreSQL username
#     'password': 'yourpassword',    # replace with your database password
#     'host': 'localhost',           # or remote host if needed
#     'port': 5432                   # default PostgreSQL port
# }
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

# MinIO configuration
MINIO_HOST = os.getenv("MINIO_HOST", "localhost:9000")
MINIO_ACCESS_KEY = os.getenv("MINIO_ACCESS_KEY", "rootuser")
MINIO_SECRET_KEY = os.getenv("MINIO_SECRET_KEY", "rootpass123")
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")

# Connect to MinIO
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
        except S3Error as e:
            print(f"Connection to MinIO failed: {e}. Retrying in 5 seconds...")
            time.sleep(5)  # Wait 5 seconds before retrying
        except Exception as e:
            print(f"Unexpected error: {e}. Retrying in 5 seconds...")
            time.sleep(5)

# Use the function to create the client with retry logic
minio_client = create_minio_client()

# Redis configuration
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
        except MaxRetryError as e:
            print(f"Max retry error encountered: {e}. Retrying in 5 seconds...")
            time.sleep(5)

# Use the function to create the client with retry logic
redis_client = create_redis_client()

# Function to connect to the PostgreSQL database
def get_sql_db_connection():
    conn = psycopg2.connect(**SQL_DATABASE)
    return conn
portgres_client = get_sql_db_connection()

def generate_hash(data):
    """Generate a unique identifier for data."""
    return hashlib.sha256(data).hexdigest()[:63]


@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        try:
            # Parse JSON payload from request
            data = request.get_json()
            if not data:
                app.logger.error("Invalid or missing JSON payload.")
                return jsonify({"error": "Invalid or missing JSON payload."}), 400
            
            # Extract fields from JSON data
            lot_id = data.get('lot_id', '000')
            date_str = data.get('date')
            start_time = data.get('start_time')
            end_time = data.get('end_time')
            phone = data.get('phone', '0000000000')
            state = data.get('state', 'CO')
            license_plate = data.get('licensePlate', '000000')
            card_number = data.get('cardNumber', '00000000')
            license_photo_base64 = data.get('licensePhoto')

            # Validate license photo (Base64)
            if not license_photo_base64:
                app.logger.error("License photo is required.")
                return jsonify({"error": "License photo is required."}), 400

            # Decode Base64 license photo
            try:
                file_data = base64.b64decode(license_photo_base64)
            except Exception as e:
                app.logger.error(f"Invalid Base64 license photo data: {e}")
                return jsonify({"error": "Invalid Base64 license photo data."}), 400

            # Generate a bucket name based on file hash
            bucket_name = generate_hash(file_data)

            # Check if bucket exists and create it if not
            if not minio_client.bucket_exists(bucket_name):
                minio_client.make_bucket(bucket_name)
                app.logger.info(f"Created bucket: {bucket_name}")
            else:
                app.logger.info(f"Bucket already exists: {bucket_name}")

            # Upload file to MinIO
            filename = f"{generate_hash(file_data)}.jpg"
            file_stream = io.BytesIO(file_data)
            minio_client.put_object(
                bucket_name,
                filename,
                file_stream,
                length=len(file_data),
                part_size=10 * 1024 * 1024,
                content_type="image/jpeg",
            )
            app.logger.info(f"Uploaded {filename} to bucket {bucket_name}")

            # Push the bucket name to Redis
            redis_client.lpush('toWorker', bucket_name)

            # Save metadata to the PostgreSQL database
            created_at = datetime.now()
            try:
                with sql_db_connection() as conn:
                    with conn.cursor() as cursor:
                        insert_query = sql.SQL("""
                            INSERT INTO transactions 
                            (lot_id, date, start_time, end_time, phone, state, license_plate, card_number, filename, created_at)
                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                            RETURNING id
                        """)
                        cursor.execute(insert_query, (
                            lot_id, date_str, start_time, end_time, phone, state, license_plate, card_number, filename, created_at
                        ))
                        conn.commit()
                        transaction_id = cursor.fetchone()[0]

                app.logger.info(f"Transaction created successfully with ID {transaction_id}")
                return jsonify({
                    "success": True,
                    "message": "Transaction created successfully.",
                    "transaction_id": transaction_id,
                    "filename": filename,
                }), 201
            except psycopg2.DatabaseError as db_err:
                app.logger.error(f"Database error: {db_err}")
                return jsonify({"error": f"Database error: {str(db_err)}"}), 500
            except Exception as e:
                app.logger.error(f"Unexpected error during database operation: {e}")
                return jsonify({"error": f"Unexpected error: {str(e)}"}), 500

        except Exception as e:
            app.logger.error(f"Unexpected error: {str(e)}")
            return jsonify({"error": f"Unexpected error: {str(e)}"}), 500

    # For GET requests, render the HTML template
    return render_template('blog/index.html')

@app.route('/records', methods=['GET'])
def get_all_transactions():
    try:
        with sql_db_connection() as conn:
            with conn.cursor() as cursor:
                # Query to select all records from the transactions table
                query = sql.SQL("SELECT * FROM transactions")
                cursor.execute(query)

                # Fetch all records
                records = cursor.fetchall()

                # Fetch column names dynamically
                column_names = [desc[0] for desc in cursor.description]

                # Convert the records into a list of dictionaries for easy JSON serialization
                transactions = []
                for record in records:
                    transaction = {}
                    for i, value in enumerate(record):
                        # Convert non-serializable types to strings
                        if isinstance(value, (date, time, datetime)):
                            transaction[column_names[i]] = value.strftime("%Y-%m-%d %H:%M:%S") if isinstance(value, datetime) else value.strftime("%H:%M:%S") if isinstance(value, time) else value.strftime("%Y-%m-%d")
                        else:
                            transaction[column_names[i]] = value
                    transactions.append(transaction)

                return jsonify({
                    "success": True,
                    "transactions": transactions
                }), 200

    except Exception as e:
        print(f"Error: {e}")
        return jsonify({"error": "Failed to fetch transactions.", "details": str(e)}), 500

if __name__ == '__main__':
    app.run(host="0.0.0.0", port=5001, debug=True)
