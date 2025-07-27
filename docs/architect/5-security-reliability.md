# 5. Security & Reliability

- Google API key only in FastAPI service (never exposed).
- All backend-to-backend traffic, never direct browser calls.
- Input validation, error handling, and rate limiting on FastAPI.
- All tool responses sanitized before UI render.

---
