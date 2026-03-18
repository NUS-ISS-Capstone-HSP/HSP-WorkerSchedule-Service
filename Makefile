PYTHON ?= python

.PHONY: install lint test-unit test coverage proto-gen swagger run docker-build

install:
	$(PYTHON) -m pip install --upgrade pip
	$(PYTHON) -m pip install -r requirements-dev.txt

lint:
	ruff check .
	mypy hsp_worker_schedule_service

test-unit:
	pytest tests/unit -q

test:
	pytest -q

coverage:
	pytest --cov=hsp_worker_schedule_service --cov-report=term-missing --cov-fail-under=70 -q

proto-gen:
	$(PYTHON) -m grpc_tools.protoc -I . --python_out=. --grpc_python_out=. rpc/echo/v1/echo.proto

swagger:
	$(PYTHON) -m scripts.generate_openapi

run:
	$(PYTHON) -m hsp_worker_schedule_service.main

docker-build:
	docker build -t hsp-execution-record-service:local .
