# Fire risk project — convenient targets
.PHONY: frontend-captures

# PNG + GIF of the web UI (needs .venv with deps from requirements.txt)
frontend-captures:
	. .venv/bin/activate && python scripts/capture_frontend_media.py
