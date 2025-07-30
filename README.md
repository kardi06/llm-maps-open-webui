# LLM Maps Open WebUI

This app is based on **Open-webui** → https://github.com/open-webui/open-webui 

But I make some changes to integrate **Google Maps functionality** with natural language interactions.

## 🎯 Overview

This project extends OpenWebUI to enable natural language interactions with Google Maps. Users can chat with local LLMs (Ollama, OpenAI-compatible models) and get Google Maps results directly embedded in their conversations - no switching between apps needed.

**Key Capabilities:**
- 🗺️ **Natural Language Maps**: "Show sushi restaurants near Senayan" → Get interactive maps with results
- 🧭 **Smart Directions**: "How do I get from SCBD to Kemang?" → Get turn-by-turn directions with map view
- 📍 **Place Discovery**: "Find coffee shops in Menteng" → Discover places with ratings, hours, and details
- 🔗 **Seamless Integration**: View results in chat or open directly in Google Maps app
- 🔒 **Secure API Handling**: Google API keys stay server-side, never exposed to browsers

## 🔌 Custom API Endpoints

I created new backend endpoints to handle Maps functionality:

**Endpoint: `/maps/find_places`**
- **Params**: location (string), query (string), type (string), radius (int)
- **Returns**: Structured place data as defined in data models

**Endpoint: `/maps/get_directions`**
- **Params**: origin (string), destination (string), mode (string)
- **Returns**: Structured directions data as defined in data models

**Endpoint: `/maps/place_details`**
- **Params**: place_id (string)
- **Returns**: Detailed place information as defined in data models

## 📁 File Locations
Based on existing OpenWebUI project structure:
- **Maps Router**: `backend/open_webui/routers/maps.py`
- **Maps Models**: `backend/open_webui/models/maps.py`
- **Google Maps client**: `backend/open_webui/utils/maps_client.py`

## 🛠️ Utility Files (maps_*)
Additional utility modules for enhanced functionality:
- `maps_security.py` - Security validation and rate limiting
- `maps_performance.py` - Performance monitoring and optimization
- `maps_circuit_breaker.py` - Circuit breaker pattern for reliability
- `maps_health.py` - Health monitoring for Maps services
- `maps_tool_registration.py` - Tool registration management

## 🔄 Data Flow
**Data Flow** [Source: docs/architect/3-data-api-flow.md]:
- Frontend → OpenWebUI Backend → Maps Router: makes request
- Maps router hits Google Maps API, returns structured results
- Integrate with existing OpenWebUI authentication and middleware

## 🔐 Security & Performance Improvements

### Security Features:
- **Input Validation & Sanitization**: All user inputs are validated and sanitized before API calls
- **Rate Limiting**: Multiple layers of rate limiting (per-minute, per-hour, per-day) to prevent abuse
- **API Key Protection**: Google Maps API keys are server-side only, never exposed to clients
- **Request Authentication**: Integrates with OpenWebUI's existing authentication system
- **Audit Logging**: Comprehensive logging of all Maps API requests for security monitoring

### Performance Enhancements:
- **Circuit Breaker Pattern**: Automatic failover when Google Maps API is unavailable
- **Connection Pooling**: Optimized HTTP connections for reduced latency
- **Timeout Management**: Configurable timeouts for different types of Maps operations
- **Performance Monitoring**: Real-time metrics tracking for request latency and success rates
- **Retry Logic**: Smart retry mechanisms with exponential backoff for failed requests

### Reliability Features:
- **Health Monitoring**: Continuous health checks for Maps services
- **Graceful Degradation**: System continues to work even when Maps services are temporarily unavailable
- **Error Handling**: Structured error responses with user-friendly messages
- **Request Deduplication**: Prevents duplicate API calls for improved efficiency

## 🧠 Development Methodology

I use **BMAD-method** for this project for context engineering, with the help of **Cursor IDE**.

This methodology helps maintain:
- Consistent code quality and architecture
- Proper documentation and testing
- Structured development workflows
- Context-aware development decisions

## 📖 Documentation

If you want to see more about the tasks, you can check:
- `docs/architect/*` - Architecture and system design documentation
- `docs/stories/*` - Development stories and implementation details  
- `docs/prd/*` - Product requirements and specifications

## 🚀 Getting Started

1. Clone this repository
2. Follow the original Open-webui setup instructions
3. Configure your Google Maps API key in environment variables
4. Run the application with the enhanced Maps functionality

## 🔧 Installing the Maps Tool in OpenWebUI

Follow these steps to install the Maps tool in your OpenWebUI interface:

### Step 1: Access OpenWebUI
- Login to your OpenWebUI interface

### Step 2: Navigate to Workspace
- Go to **Workspace** section in OpenWebUI

### Step 3: Create New Tool
- Click on **Tools** tab
- Click **Create New Tool**

### Step 4: Copy Maps Tool Code
- Copy all the code from `backend/open_webui/tools/maps_tool.py`
- Paste it into the new tool editor in OpenWebUI
- Save the tool

### Step 5: Enable Tool in Chat
- When using chat, don't forget to **checklist the Maps tool** to enable it
- The tool will now be available for natural language Maps interactions

### ⚠️ Important Notes:
- Make sure your Google Maps API key is properly configured in your environment variables
- The Maps tool requires the backend services to be running for full functionality
- Test the tool with simple queries like "Find restaurants near me" to verify installation

---

*Built on top of the excellent [Open-webui](https://github.com/open-webui/open-webui) project with enhanced Maps integration capabilities.*


