# 2. System Overview

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
