CODE_PATHS=resource/* moj_analytics/* tests/*

.PHONY: check_format lint format test help all


all: help


## format: format code using black
format:
	black ${CODE_PATHS}


## check_format: check formatting using black
check_format:
	black --check ${CODE_PATHS}


## lint: lint code using flake8
lint:
	flake8 ${CODE_PATHS} --count --show-source --statistics --ignore=E501,W503 && echo "Success"


## test: run tests using pytest
test:
	pytest


## help: show makefile help
help: Makefile
	@echo
	@echo "Commands:"
	@echo
	@sed -n 's/^##//p' $< | column -t -s ':' | sed -e 's/^/ /'
	@echo
