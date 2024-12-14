VERSION=v1
DOCKERUSER=shso9201

build:
	docker build -f Dockerfile -t openalpr-worker .
push:
	docker tag openalpr-worker $(DOCKERUSER)/openalpr-worker:$(VERSION)
	docker push $(DOCKERUSER)/openalpr-worker:$(VERSION)
	docker tag openalpr-worker $(DOCKERUSER)/openalpr-worker:latest
	docker push $(DOCKERUSER)/openalpr-worker:latest

