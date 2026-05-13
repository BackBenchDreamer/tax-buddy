# API Key Management System

## Overview

Tax Buddy now supports secure, user-friendly API key management for Groq AI services. Users can provide their own API keys through the UI, which are stored securely in browser session storage and never persisted to disk or server databases.

## Architecture

### Design Principles

1. **Security First**: Keys are never logged, exposed in responses, or stored permanently
2. **User Choice**: Support both user-provided keys and server-side defaults
3. **Graceful Degradation**: AI features work with server keys or disable cleanly without them
4. **Session-Based**: User keys are cleared when the browser closes
5. **Backward Compatible**: Existing server-side `.env` configuration still works

### Key Flow

```
User enters API key in UI
    ↓
Frontend validates format
    ↓
Backend tests key with Groq API
    ↓
If valid: Store in thread-local storage
    ↓
All AI operations use: user key → server key → none
    ↓
Key cleared on browser close or manual clear
```

## Backend Implementation

### 1. API Endpoints

#### `POST /api/v1/config/api-key`
Set user's API key for the current session.

**Request:**
```json
{
  "api_key": "gsk_..."
}
```

**Response:**
```json
{
  "valid": true,
  "message": "API key configured successfully",
  "model": "llama-3.3-70b-versatile"
}
```

**Security:**
- Key is validated before acceptance
- Key is never logged or returned in responses
- Stored in thread-local storage (request-scoped)

#### `GET /api/v1/config/api-key/status`
Check if an API key is configured and its source.

**Response:**
```json
{
  "configured": true,
  "source": "user",  // "user", "server", or "none"
  "model": "llama-3.3-70b-versatile"
}
```

#### `DELETE /api/v1/config/api-key`
Clear user's API key from the current session.

**Response:**
```json
{
  "message": "API key cleared successfully"
}
```

#### `POST /api/v1/config/api-key/test`
Test an API key without storing it.

**Request:**
```json
{
  "api_key": "gsk_..."
}
```

**Response:**
```json
{
  "valid": true,
  "message": "API key is valid and working",
  "model": "llama-3.3-70b-versatile"
}
```

### 2. Groq Service Updates

**File:** `backend/app/services/groq_service.py`

#### Thread-Local Storage
```python
import threading
_thread_local = threading.local()

def set_user_api_key(api_key: Optional[str]):
    """Set API key for current request context."""
    _thread_local.user_api_key = api_key

def get_user_api_key() -> Optional[str]:
    """Get API key from current request context."""
    return getattr(_thread_local, 'user_api_key', None)
```

#### Key Priority
1. Explicit parameter passed to function
2. Thread-local storage (user-provided key)
3. Server configuration (`.env` file)
4. None (AI features disabled)

#### Key Testing
```python
async def test_api_key(api_key: str) -> Dict[str, Any]:
    """Test if an API key is valid by making a simple API call."""
    # Makes minimal API call to verify key works
    # Returns {"valid": bool, "message": str, "model": str}
```

### 3. Schema Definitions

**File:** `backend/app/schemas/schemas.py`

```python
class ApiKeyRequest(BaseModel):
    api_key: str = Field(..., min_length=20)

class ApiKeyStatusResponse(BaseModel):
    configured: bool
    source: str  # "user", "server", or "none"
    model: Optional[str]

class ApiKeyTestResponse(BaseModel):
    valid: bool
    message: str
    model: Optional[str]
```

## Frontend Implementation

### 1. Components

#### `ApiKeyInput.tsx`
Reusable component for API key input with:
- Show/hide toggle for key visibility
- Test connection button
- Save button with validation
- Clear button
- Real-time status feedback
- Link to Groq Console

**Features:**
- Password-style input with eye icon toggle
- Validates key format before submission
- Tests key with backend before saving
- Stores configuration flag in sessionStorage
- Visual feedback (success/error states)

#### `Settings.tsx`
Full settings page with:
- Current API key status display
- API key configuration section
- Security & privacy information
- Help and troubleshooting guide

**Status Display:**
- Shows if key is configured
- Indicates source (user/server/none)
- Displays current model
- Warns if AI features are disabled

### 2. Settings Page

**File:** `frontend/app/settings/page.tsx`

Simple Next.js page that renders the Settings component.

### 3. Navigation

**Updated:** `frontend/app/page.tsx`

Added Settings link in the header navigation:
```tsx
<Link href="/settings" className="...">
  <SettingsIcon className="w-4 h-4" />
  <span className="hidden sm:inline">Settings</span>
</Link>
```

## Security Considerations

### What We Do

✅ **Store keys in sessionStorage** - Cleared when browser closes
✅ **Never log API keys** - Keys are sanitized from all logs
✅ **Validate before storage** - Test key with Groq API first
✅ **Thread-local storage** - Keys are request-scoped on backend
✅ **No database persistence** - Keys never written to disk
✅ **HTTPS in production** - All communication encrypted
✅ **Clear on logout** - Manual clear button available

### What We Don't Do

❌ **Never store in localStorage** - Would persist across sessions
❌ **Never log keys** - Not in console, files, or error messages
❌ **Never expose in responses** - API never returns the key
❌ **Never persist to database** - Keys are ephemeral
❌ **Never send unnecessarily** - Only sent when setting/testing

### Threat Model

| Threat | Mitigation |
|--------|-----------|
| XSS attacks | sessionStorage is origin-scoped; sanitize all inputs |
| Network interception | Use HTTPS in production |
| Server-side logging | Keys never logged; sanitized from error messages |
| Database breach | Keys never stored in database |
| Session hijacking | Keys cleared on browser close; short-lived |

## Usage Guide

### For End Users

1. **Get a Groq API Key:**
   - Visit [console.groq.com](https://console.groq.com/keys)
   - Sign up or log in
   - Create a new API key
   - Copy the key (starts with `gsk_`)

2. **Configure in Tax Buddy:**
   - Click "Settings" in the top navigation
   - Paste your API key in the input field
   - Click "Test Connection" to verify
   - Click "Save API Key" to activate

3. **Using AI Features:**
   - AI validation and optimization now use your key
   - Your usage is tracked in your Groq account
   - Key is active until you close the browser

4. **Clearing Your Key:**
   - Click "Clear" button in Settings
   - Or simply close your browser

### For Self-Hosted Deployments

#### Option 1: Server-Side Key (Recommended for Single User)

Set in `backend/.env`:
```bash
GROQ_API_KEY=gsk_your_key_here
GROQ_MODEL=llama-3.3-70b-versatile
GROQ_TIMEOUT=30
```

All users share this key. No UI configuration needed.

#### Option 2: User-Provided Keys (Recommended for Multi-User)

Don't set `GROQ_API_KEY` in `.env`. Users must provide their own keys through the UI.

#### Option 3: Hybrid (Best of Both)

Set a default key in `.env` for convenience. Users can optionally override with their own keys.

## API Examples

### Test a Key (cURL)

```bash
curl -X POST http://localhost:8000/api/v1/config/api-key/test \
  -H "Content-Type: application/json" \
  -d '{"api_key": "gsk_..."}'
```

### Set a Key

```bash
curl -X POST http://localhost:8000/api/v1/config/api-key \
  -H "Content-Type: application/json" \
  -d '{"api_key": "gsk_..."}'
```

### Check Status

```bash
curl http://localhost:8000/api/v1/config/api-key/status
```

### Clear Key

```bash
curl -X DELETE http://localhost:8000/api/v1/config/api-key
```

## Troubleshooting

### "Invalid API key" Error

**Causes:**
- Key is incorrect or expired
- Key doesn't have required permissions
- Groq API is down

**Solutions:**
1. Verify key in Groq Console
2. Generate a new key
3. Check Groq status page

### "API key test failed" Error

**Causes:**
- Network connectivity issues
- Backend server not running
- Groq API timeout

**Solutions:**
1. Check backend is running on port 8000
2. Verify internet connection
3. Try again in a few moments

### AI Features Not Working

**Causes:**
- No API key configured
- Key has no credits/quota
- Rate limit exceeded

**Solutions:**
1. Check Settings page for key status
2. Verify Groq account has credits
3. Wait for rate limit to reset

### Key Not Persisting

**Expected Behavior:**
- Keys are stored in sessionStorage
- Cleared when browser closes
- This is intentional for security

**If you want persistence:**
- Use server-side key in `.env` instead

## Development

### Running Tests

```bash
# Backend
cd backend
python -m pytest tests/test_api_key_management.py

# Frontend
cd frontend
npm test -- ApiKeyInput.test.tsx
```

### Adding New AI Features

When adding new AI-powered features:

1. Use `_get_groq_client()` to get client
2. Don't pass API key explicitly (uses thread-local)
3. Handle `None` return gracefully
4. Log warnings, not errors, when key missing

Example:
```python
from app.services.groq_service import _get_groq_client

async def my_ai_feature(text: str):
    client = _get_groq_client()
    if not client:
        log.warning("AI feature disabled - no API key")
        return None
    
    # Use client...
```

## Future Enhancements

### Potential Improvements

1. **Key Encryption**: Encrypt keys in sessionStorage with Web Crypto API
2. **Multiple Providers**: Support OpenAI, Anthropic, etc.
3. **Usage Tracking**: Show user their API usage statistics
4. **Key Rotation**: Automatic key rotation for server keys
5. **Team Keys**: Support for organization-level keys
6. **Key Validation**: More robust format validation
7. **Rate Limiting**: Client-side rate limit tracking

### Not Planned

- ❌ Database storage of user keys (security risk)
- ❌ localStorage persistence (security risk)
- ❌ Automatic key sharing between users (privacy risk)

## Deployment Considerations

### Production Checklist

- [ ] Set `GROQ_API_KEY` in production `.env` (optional)
- [ ] Enable HTTPS for all API communication
- [ ] Configure CORS for frontend domain
- [ ] Set appropriate rate limits
- [ ] Monitor API usage and costs
- [ ] Document key management for users
- [ ] Test key validation flow
- [ ] Verify keys are never logged

### Environment Variables

```bash
# Required for AI features (if not using user keys)
GROQ_API_KEY=gsk_...

# Optional - defaults shown
GROQ_MODEL=llama-3.3-70b-versatile
GROQ_TIMEOUT=30
```

### Docker Deployment

Keys can be passed via environment variables:

```bash
docker run -e GROQ_API_KEY=gsk_... tax-buddy
```

Or mounted as secrets:

```yaml
# docker-compose.yml
services:
  backend:
    environment:
      - GROQ_API_KEY_FILE=/run/secrets/groq_key
    secrets:
      - groq_key

secrets:
  groq_key:
    external: true
```

## Support

For issues or questions:
- Check this documentation first
- Review Settings page help section
- Check backend logs for errors
- Verify Groq API status
- Open GitHub issue with details

## License

This feature is part of Tax Buddy and follows the same license as the main project.

---

**Last Updated:** 2026-05-13
**Version:** 1.0.0
**Status:** Production Ready ✅