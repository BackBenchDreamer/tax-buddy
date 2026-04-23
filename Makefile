BACKEND_DIR=backend
FRONTEND_DIR=frontend

.PHONY: backend-dev frontend-dev

backend-dev:
	cd $(BACKEND_DIR) && uvicorn app.main:app --reload --port 8000

frontend-dev:
	cd $(FRONTEND_DIR) && npm run dev
