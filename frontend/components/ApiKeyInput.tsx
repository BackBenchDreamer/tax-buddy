'use client';

import { useState } from 'react';
import { Eye, EyeOff, Key, CheckCircle, XCircle, Loader2 } from 'lucide-react';

interface ApiKeyInputProps {
  onKeySet?: (success: boolean) => void;
}

export default function ApiKeyInput({ onKeySet }: ApiKeyInputProps) {
  const [apiKey, setApiKey] = useState('');
  const [showKey, setShowKey] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [status, setStatus] = useState<{
    type: 'idle' | 'success' | 'error';
    message: string;
  }>({ type: 'idle', message: '' });

  const handleTest = async () => {
    if (!apiKey.trim()) {
      setStatus({ type: 'error', message: 'Please enter an API key' });
      return;
    }

    setIsLoading(true);
    setStatus({ type: 'idle', message: '' });

    try {
      const response = await fetch('http://localhost:8000/api/v1/config/api-key/test', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ api_key: apiKey }),
      });

      const data = await response.json();

      if (response.ok && data.valid) {
        setStatus({
          type: 'success',
          message: `✓ API key is valid (Model: ${data.model})`,
        });
      } else {
        setStatus({
          type: 'error',
          message: data.message || 'Invalid API key',
        });
      }
    } catch (error) {
      setStatus({
        type: 'error',
        message: 'Failed to test API key. Is the backend running?',
      });
    } finally {
      setIsLoading(false);
    }
  };

  const handleSave = async () => {
    if (!apiKey.trim()) {
      setStatus({ type: 'error', message: 'Please enter an API key' });
      return;
    }

    setIsLoading(true);
    setStatus({ type: 'idle', message: '' });

    try {
      const response = await fetch('http://localhost:8000/api/v1/config/api-key', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ api_key: apiKey }),
      });

      const data = await response.json();

      if (response.ok && data.valid) {
        setStatus({
          type: 'success',
          message: '✓ API key saved successfully!',
        });
        
        // Store in sessionStorage (cleared on browser close)
        sessionStorage.setItem('groq_api_key_configured', 'true');
        
        onKeySet?.(true);
      } else {
        setStatus({
          type: 'error',
          message: data.message || data.detail || 'Failed to save API key',
        });
        onKeySet?.(false);
      }
    } catch (error) {
      setStatus({
        type: 'error',
        message: 'Failed to save API key. Is the backend running?',
      });
      onKeySet?.(false);
    } finally {
      setIsLoading(false);
    }
  };

  const handleClear = async () => {
    setIsLoading(true);
    
    try {
      await fetch('http://localhost:8000/api/v1/config/api-key', {
        method: 'DELETE',
      });
      
      setApiKey('');
      sessionStorage.removeItem('groq_api_key_configured');
      setStatus({
        type: 'success',
        message: 'API key cleared',
      });
      onKeySet?.(false);
    } catch (error) {
      setStatus({
        type: 'error',
        message: 'Failed to clear API key',
      });
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="space-y-4">
      <div className="flex items-start gap-3">
        <Key className="w-5 h-5 text-blue-400 mt-3" />
        <div className="flex-1">
          <label htmlFor="api-key" className="block text-sm font-medium text-slate-200 mb-2">
            Groq API Key
          </label>
          <div className="relative">
            <input
              id="api-key"
              type={showKey ? 'text' : 'password'}
              value={apiKey}
              onChange={(e) => setApiKey(e.target.value)}
              placeholder="gsk_..."
              className="w-full px-4 py-2.5 bg-slate-800/50 border border-slate-700 rounded-lg text-slate-100 placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent pr-12"
              disabled={isLoading}
            />
            <button
              type="button"
              onClick={() => setShowKey(!showKey)}
              className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-300 transition-colors"
              disabled={isLoading}
            >
              {showKey ? <EyeOff className="w-5 h-5" /> : <Eye className="w-5 h-5" />}
            </button>
          </div>
          
          {status.message && (
            <div
              className={`mt-2 flex items-center gap-2 text-sm ${
                status.type === 'success'
                  ? 'text-green-400'
                  : status.type === 'error'
                  ? 'text-red-400'
                  : 'text-slate-400'
              }`}
            >
              {status.type === 'success' && <CheckCircle className="w-4 h-4" />}
              {status.type === 'error' && <XCircle className="w-4 h-4" />}
              <span>{status.message}</span>
            </div>
          )}

          <p className="mt-2 text-xs text-slate-400">
            Get your API key from{' '}
            <a
              href="https://console.groq.com/keys"
              target="_blank"
              rel="noopener noreferrer"
              className="text-blue-400 hover:text-blue-300 underline"
            >
              Groq Console
            </a>
            . Your key is stored securely in your browser session only.
          </p>
        </div>
      </div>

      <div className="flex gap-3">
        <button
          onClick={handleTest}
          disabled={isLoading || !apiKey.trim()}
          className="px-4 py-2 bg-slate-700 hover:bg-slate-600 text-slate-100 rounded-lg font-medium transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
        >
          {isLoading ? (
            <Loader2 className="w-4 h-4 animate-spin" />
          ) : (
            'Test Connection'
          )}
        </button>

        <button
          onClick={handleSave}
          disabled={isLoading || !apiKey.trim()}
          className="px-4 py-2 bg-blue-600 hover:bg-blue-500 text-white rounded-lg font-medium transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
        >
          {isLoading ? (
            <Loader2 className="w-4 h-4 animate-spin" />
          ) : (
            'Save API Key'
          )}
        </button>

        {apiKey && (
          <button
            onClick={handleClear}
            disabled={isLoading}
            className="px-4 py-2 bg-red-600/20 hover:bg-red-600/30 text-red-400 rounded-lg font-medium transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          >
            Clear
          </button>
        )}
      </div>
    </div>
  );
}

// Made with Bob
