VERSION=v1
DOCKERUSER=shso9201

build:
	docker build -f Dockerfile -t parking-rest .

push:
	docker tag parking-rest $(DOCKERUSER)/parking-rest:$(VERSION)
	docker push $(DOCKERUSER)/parking-rest:$(VERSION)
	docker tag parking-rest $(DOCKERUSER)/parking-rest:latest
	docker push $(DOCKERUSER)/parking-rest:latest
