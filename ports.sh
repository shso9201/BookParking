#!/bin/sh

kubectl port-forward --namespace minio-ns svc/minio-proj 9000:9000 &
kubectl port-forward --namespace minio-ns svc/minio-proj 9001:9001 &
kubectl port-forward svc/redis 6379:6379 &
kubectl port-forward svc/postgres 5432:5432 &

