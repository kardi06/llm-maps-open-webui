# 4. Agent API Contracts

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
