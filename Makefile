.PHONY: setup dev build test lint clean

setup:
	bash scripts/setup.sh

dev:
	docker-compose up

build:
	docker-compose build

test:
	docker-compose run backend pytest
	cd frontend && npm run test

lint:
	cd frontend && npm run lint
	cd backend && flake8 . && mypy .

clean:
	docker-compose down -v
	rm -rf frontend/node_modules frontend/.next
	rm -rf backend/__pycache__ backend/.pytest_cache
