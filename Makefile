USER_ID=$(shell id -u)
GIT_COMMIT_ID=$(shell git describe --always --dirty)
GIT_BRANCH_NAME=$(shell git rev-parse --abbrev-ref HEAD | sed "s/[^[:alnum:]]//g")

.PHONY: container_tag
container_tag:
	@echo $(GIT_COMMIT_ID)-$(GIT_BRANCH_NAME)

build_web_dist:
	docker buildx build \
		--platform=linux/arm64
		--build-arg COMMIT_ID=$(GIT_COMMIT_ID) \
		--target dist \
		-t $(GRAND_CHALLENGE_PRIVATE_REPOSITORY_WEB_URI):$(GIT_COMMIT_ID)-$(GIT_BRANCH_NAME) \
		.

push_web_dist:
	docker push $(GRAND_CHALLENGE_PRIVATE_REPOSITORY_WEB_URI):$(GIT_COMMIT_ID)-$(GIT_BRANCH_NAME)

push_staging: build_web_dist
	docker tag $(GRAND_CHALLENGE_PRIVATE_REPOSITORY_WEB_URI):$(GIT_COMMIT_ID)-$(GIT_BRANCH_NAME) $(GRAND_CHALLENGE_WEB_STAGING_REPOSITORY_URI):$(GIT_COMMIT_ID)-$(GIT_BRANCH_NAME)
	aws ecr get-login-password --region $(GRAND_CHALLENGE_STAGING_REGION) --profile $(GRAND_CHALLENGE_STAGING_PROFILE) | docker login --username AWS --password-stdin $(GRAND_CHALLENGE_STAGING_ECR_HOST)
	docker push $(GRAND_CHALLENGE_WEB_STAGING_REPOSITORY_URI):$(GIT_COMMIT_ID)-$(GIT_BRANCH_NAME)

migrate:
	docker compose run --rm gc.localhost python manage.py migrate

check_migrations:
	docker compose run --rm gc.localhost python manage.py makemigrations --dry-run --check

migrations:
	docker compose run -u $(USER_ID) --rm gc.localhost python manage.py makemigrations

runserver: development_fixtures
	bash -c "trap 'docker compose down' EXIT; docker compose up"

rundeps:
	bash -c "trap 'docker compose down' EXIT; docker compose up postgres s3.localhost redis registry"

local_s3:
	docker compose run \
		-v $(shell readlink -f ./scripts/):/app/scripts:ro \
		--rm \
		gc.localhost \
		bash -c "python manage.py runscript local_s3"

development_fixtures:
	docker compose run \
		-v $(shell readlink -f ./scripts/):/app/scripts:ro \
		--rm \
		gc.localhost \
		bash -c "python manage.py runscript local_s3 && python manage.py migrate && python manage.py runscript development_fixtures"

algorithm_evaluation_fixtures:
	docker compose run \
		-v $(shell readlink -f ./scripts/):/app/scripts:ro \
		--rm \
		gc.localhost \
		python manage.py runscript algorithm_evaluation_fixtures

external_algorithm_evaluation_fixtures:
	docker compose run \
		-v $(shell readlink -f ./scripts/):/app/scripts:ro \
		--rm \
		gc.localhost \
		python manage.py runscript external_algorithm_evaluation_fixtures

cost_fixtures:
	docker compose run \
		-v $(shell readlink -f ./scripts/):/app/scripts:ro \
		--rm \
		gc.localhost \
		python manage.py runscript cost_fixtures

component_interface_value_fixtures:
	docker compose run \
		-v $(shell readlink -f ./scripts/):/app/scripts:ro \
		--rm \
		gc.localhost \
		python manage.py runscript component_interface_value_fixtures

superuser:
	docker compose run \
		-v $(shell readlink -f ./scripts/):/app/scripts:ro \
		--rm \
		gc.localhost \
		python manage.py runscript create_superuser

docpages:
	docker compose run \
		-v $(shell readlink -f ./scripts/):/app/scripts:ro \
		--rm \
		gc.localhost \
		python manage.py runscript create_docpages

.PHONY: docs
docs:
	docker compose run --rm -u $(USER_ID) gc.localhost bash -c "cd docs && make html"
