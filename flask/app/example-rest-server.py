from flask import Flask, request, jsonify, send_file
from minio import Minio
from minio.error import S3Error
import os
import jsonpickle
import io
import redis
import base64
import hashlib
import time 


app = Flask(__name__)

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


def generate_songhash(audio_data):
    """Generate a unique identifier for a song."""
    return hashlib.sha256(audio_data).hexdigest()[:63]

@app.route('/apiv1/separate', methods=['POST'])
def separate():
    data = request.json
    song_data = base64.b64decode(data['mp3'])  # Decode base64 data
    model = data.get('model', 'default')  # Model can be specified optionally
    callback = data.get('callback', None)  # Optional callback URL

    # Generate a unique identifier for the song
    songhash = generate_songhash(song_data)

    MINIO_BUCKET_NAME = songhash
    # Ensure the bucket exists
    if not minio_client.bucket_exists(MINIO_BUCKET_NAME):
        minio_client.make_bucket(MINIO_BUCKET_NAME)

    # Store the original song in MinIO
    song_filename = f"{songhash}.mp3"
    minio_client.put_object(
        MINIO_BUCKET_NAME,
        song_filename,
        io.BytesIO(song_data),
        length=len(song_data),
        content_type="audio/mpeg"
    )

    # Queue the song in Redis
    redis_client.lpush('toWorker', songhash)

    response = {
        "hash": songhash,
        "reason": "Song enqueued for separation"
    }
    return jsonify(response)

@app.route('/apiv1/queue', methods=['GET'])
def get_queue():
    queue = redis_client.lrange('toWorker', 0, -1)
    queue = [item.decode("utf-8") for item in queue]
    return jsonify({"queue": queue})

@app.route('/apiv1/track/<songhash>/<track>', methods=['GET'])
def get_track(songhash, track):
    # Construct the filename for the track
    track_filename = f"{songhash}/{track}.mp3"

    try:
        # Retrieve the track from MinIO
        response = minio_client.get_object(MINIO_BUCKET_NAME, track_filename)
        return send_file(
            io.BytesIO(response.read()),
            mimetype='audio/mpeg',
            as_attachment=True,
            download_name=f"{track}.mp3"
        )
    except S3Error as e:
        return jsonify({"error": str(e)}), 404

@app.route('/apiv1/remove/<songhash>/<track>', methods=['DELETE'])
def remove_track(songhash, track):
    track_filename = f"{songhash}/{track}.mp3"
    try:
        minio_client.remove_object(MINIO_BUCKET_NAME, track_filename)
        return jsonify({"status": "success", "message": f"Track {track} removed."})
    except S3Error as e:
        return jsonify({"error": str(e)}), 404

@app.route('/', methods=['GET'])
def hello():
    return '<h1> Music Separation Server</h1><p> Use a valid endpoint </p>'

if __name__ == '__main__':
    app.run(host="0.0.0.0", port=5000)
