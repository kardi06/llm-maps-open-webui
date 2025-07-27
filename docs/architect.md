# Architecture: OpenWebUI LLM Maps Agent

---

## 1. Objective

Enable users to chat with a local LLM (Ollama/Llama3/OpenAI) in OpenWebUI and get real-time, embedded Google Maps results (places, directions) securely, by proxying through a Python FastAPI agent.

---

## 2. System Overview

- **Frontend:** OpenWebUI (Svelte)
  - Displays chat, parses tool call responses for map results.
  - Renders maps using Google Maps Embed or widget.

- **Backend:** OpenWebUI Python Service
  - Manages sessions and user input.
  - Connects to LLM (Ollama/OpenAI) with tool/function-calling enabled.
  - Registers and invokes tools (find_places, get_directions) via FastAPI.

- **Map Agent Service:** FastAPI (Python)
  - Endpoints: `/find_places`, `/get_directions`, `/place_details`.
  - Handles all Google Maps API requests, secures API key, applies rate limits and validation.
  - Sends clean data back to OpenWebUI backend.

- **LLM:** Ollama/Llama3 or OpenAI API.
  - Must support function/tool calling, able to pass parameters from prompt.

---

## 3. Data & API Flow

1. User enters a prompt (e.g., “Show sushi near Senayan”).
2. Frontend sends prompt to backend.
3. Backend LLM parses intent, triggers `find_places` tool call.
4. Backend → FastAPI agent: makes request.
5. Agent hits Google Maps API, returns structured results.
6. Backend passes results to frontend.
7. Frontend renders map/list, adds “Open in Google Maps” links.

---

## 4. Agent API Contracts

### `/find_places`
- **Params:** `location`, `query`, `type`, `radius`
- **Returns:** name, address, lat/lng, place_id, rating, open_now, maps_url

### `/get_directions`
- **Params:** `origin`, `destination`, `mode`
- **Returns:** steps, distance, duration, maps_url

### `/place_details` (optional)
- **Params:** `place_id`
- **Returns:** details, reviews, photos, maps_url

---

## 5. Security & Reliability

- Google API key only in FastAPI service (never exposed).
- All backend-to-backend traffic, never direct browser calls.
- Input validation, error handling, and rate limiting on FastAPI.
- All tool responses sanitized before UI render.

---

## 6. Extensibility

- New tool endpoints: just register in backend and implement in agent.
- Map provider swap: refactor agent to plug in Mapbox, OSM, etc.
- Richer UX: add marker clicks, user location, directions steps in Svelte.

---

## 7. Roadmap

- [ ] Scaffold FastAPI agent endpoints.
- [ ] Register functions/tools in OpenWebUI backend.
- [ ] Build Svelte map rendering component.
- [ ] End-to-end test: LLM → tool → agent → maps.
- [ ] Harden, log, and iterate.

---

