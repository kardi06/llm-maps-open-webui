# 3. Data & API Flow

1. User enters a prompt (e.g., “Show sushi near Senayan”).
2. Frontend sends prompt to backend.
3. Backend LLM parses intent, triggers `find_places` tool call.
4. Backend → FastAPI agent: makes request.
5. Agent hits Google Maps API, returns structured results.
6. Backend passes results to frontend.
7. Frontend renders map/list, adds “Open in Google Maps” links.

---
