#!/bin/sh

helm install -f minio/minio-config.yaml -n minio-ns --create-namespace minio-proj bitnami/minio

kubectl apply -f minio/minio-external-service.yaml

kubectl apply -f redis/redis-deployment.yaml

kubectl apply -f postgres/postgres-pv.yaml

kubectl apply -f postgres/postgres-pvc.yaml

kubectl apply -f postgres/postgres-deployment.yaml

kubectl apply -f postgres/postgres-service.yaml

kubectl apply -f worker/worker-deployment.yaml

