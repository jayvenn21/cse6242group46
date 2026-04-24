# Fire risk project — convenient targets
.PHONY: frontend-snapshot frontend-snapshot-zip frontend-captures

# Copy frontend + data files into outputs/frontend-snapshot/ (self-contained for static hosting)
frontend-snapshot:
	python3 scripts/sync_frontend_data.py

# Same, plus outputs/frontend-snapshot.zip
frontend-snapshot-zip:
	python3 scripts/sync_frontend_data.py --zip

# PNG + GIF of the live UI (Playwright; use .venv with requirements.txt)
frontend-captures:
	. .venv/bin/activate && python scripts/capture_frontend_media.py
