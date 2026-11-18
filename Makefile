.PHONY: help backend-sync backend-run backend-sync-data backend-lint backend-format backend-test backend-ci ios-build

help:
	@echo "Available targets:"
	@echo "  backend-sync    Install backend deps with uv"
	@echo "  backend-run     Run backend API locally"
	@echo "  backend-sync-data  Sync MOENV toilets into DB"
	@echo "  backend-lint    Run ruff lint checks"
	@echo "  backend-format  Format backend code with ruff"
	@echo "  backend-test    Run backend tests"
	@echo "  backend-ci      Run lint + tests (CI-equivalent)"
	@echo "  ios-build       Compile the iPhone app without signing"

backend-sync:
	cd backend && uv sync --dev

backend-run:
	cd backend && uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

backend-sync-data:
	cd backend && uv run python -m app.ingestion.sync_moenv

backend-lint:
	cd backend && uv run ruff check .

backend-format:
	cd backend && uv run ruff format .

backend-test:
	cd backend && uv run pytest tests -q
	node --test backend/tests/web_security.test.cjs

backend-ci: backend-lint backend-test

ios-build:
	xcodebuild -project ios/ToiletMap.xcodeproj -scheme ToiletMap -configuration Debug -sdk iphoneos -destination 'generic/platform=iOS' -derivedDataPath ios/build CODE_SIGNING_ALLOWED=NO build
