'use client';

import { useState, useEffect } from 'react';
import { Settings as SettingsIcon, AlertCircle, CheckCircle, Server } from 'lucide-react';
import ApiKeyInput from './ApiKeyInput';

export default function Settings() {
  const [keyStatus, setKeyStatus] = useState<{
    configured: boolean;
    source: 'user' | 'server' | 'none';
    model: string | null;
  } | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  const fetchKeyStatus = async () => {
    setIsLoading(true);
    try {
      const response = await fetch('http://localhost:8000/api/v1/config/api-key/status');
      if (response.ok) {
        const data = await response.json();
        setKeyStatus(data);
      }
    } catch (error) {
      console.error('Failed to fetch API key status:', error);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchKeyStatus();
  }, []);

  const handleKeySet = (success: boolean) => {
    if (success) {
      // Refresh status after key is set
      setTimeout(fetchKeyStatus, 500);
    }
  };

  return (
    <div className="max-w-4xl mx-auto p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center gap-3 mb-8">
        <SettingsIcon className="w-8 h-8 text-blue-400" />
        <div>
          <h1 className="text-3xl font-bold text-slate-100">Settings</h1>
          <p className="text-slate-400 mt-1">Configure your Tax Buddy preferences</p>
        </div>
      </div>

      {/* Current Status Card */}
      <div className="bg-slate-800/50 border border-slate-700 rounded-xl p-6">
        <h2 className="text-xl font-semibold text-slate-100 mb-4 flex items-center gap-2">
          <Server className="w-5 h-5 text-blue-400" />
          API Configuration Status
        </h2>

        {isLoading ? (
          <div className="text-slate-400">Loading status...</div>
        ) : keyStatus ? (
          <div className="space-y-3">
            <div className="flex items-center gap-3">
              {keyStatus.configured ? (
                <CheckCircle className="w-5 h-5 text-green-400" />
              ) : (
                <AlertCircle className="w-5 h-5 text-yellow-400" />
              )}
              <div>
                <p className="text-slate-200 font-medium">
                  {keyStatus.configured ? 'API Key Configured' : 'No API Key Configured'}
                </p>
                <p className="text-sm text-slate-400">
                  Source:{' '}
                  <span className="font-mono text-slate-300">
                    {keyStatus.source === 'user'
                      ? 'User-provided (Session)'
                      : keyStatus.source === 'server'
                      ? 'Server Configuration'
                      : 'Not configured'}
                  </span>
                </p>
                {keyStatus.model && (
                  <p className="text-sm text-slate-400">
                    Model: <span className="font-mono text-slate-300">{keyStatus.model}</span>
                  </p>
                )}
              </div>
            </div>

            {keyStatus.source === 'server' && (
              <div className="mt-4 p-4 bg-blue-500/10 border border-blue-500/30 rounded-lg">
                <p className="text-sm text-blue-300">
                  ℹ️ You're using the server's default API key. You can optionally provide your own
                  key below for personalized usage.
                </p>
              </div>
            )}

            {!keyStatus.configured && (
              <div className="mt-4 p-4 bg-yellow-500/10 border border-yellow-500/30 rounded-lg">
                <p className="text-sm text-yellow-300">
                  ⚠️ AI features are currently disabled. Please configure an API key below to enable
                  AI-powered validation and tax optimization.
                </p>
              </div>
            )}
          </div>
        ) : (
          <div className="text-red-400">Failed to load status</div>
        )}
      </div>

      {/* API Key Configuration Card */}
      <div className="bg-slate-800/50 border border-slate-700 rounded-xl p-6">
        <h2 className="text-xl font-semibold text-slate-100 mb-4">Configure Your API Key</h2>
        
        <div className="mb-6 p-4 bg-slate-700/30 border border-slate-600 rounded-lg">
          <h3 className="text-sm font-semibold text-slate-200 mb-2">Why provide your own API key?</h3>
          <ul className="text-sm text-slate-400 space-y-1 list-disc list-inside">
            <li>Use your own Groq API quota and rate limits</li>
            <li>Keep your usage separate from server defaults</li>
            <li>Full control over your AI interactions</li>
            <li>Key is stored only in your browser session (cleared on close)</li>
          </ul>
        </div>

        <ApiKeyInput onKeySet={handleKeySet} />
      </div>

      {/* Security Notice */}
      <div className="bg-slate-800/30 border border-slate-700/50 rounded-xl p-6">
        <h3 className="text-lg font-semibold text-slate-100 mb-3 flex items-center gap-2">
          🔒 Security & Privacy
        </h3>
        <ul className="text-sm text-slate-400 space-y-2">
          <li className="flex items-start gap-2">
            <span className="text-green-400 mt-0.5">✓</span>
            <span>Your API key is stored only in your browser's session storage</span>
          </li>
          <li className="flex items-start gap-2">
            <span className="text-green-400 mt-0.5">✓</span>
            <span>Keys are automatically cleared when you close your browser</span>
          </li>
          <li className="flex items-start gap-2">
            <span className="text-green-400 mt-0.5">✓</span>
            <span>Keys are never logged or stored on the server</span>
          </li>
          <li className="flex items-start gap-2">
            <span className="text-green-400 mt-0.5">✓</span>
            <span>All API communication uses HTTPS in production</span>
          </li>
          <li className="flex items-start gap-2">
            <span className="text-green-400 mt-0.5">✓</span>
            <span>You can clear your key at any time using the "Clear" button</span>
          </li>
        </ul>
      </div>

      {/* Help Section */}
      <div className="bg-slate-800/30 border border-slate-700/50 rounded-xl p-6">
        <h3 className="text-lg font-semibold text-slate-100 mb-3">Need Help?</h3>
        <div className="text-sm text-slate-400 space-y-2">
          <p>
            <strong className="text-slate-300">How to get a Groq API key:</strong>
          </p>
          <ol className="list-decimal list-inside space-y-1 ml-2">
            <li>Visit <a href="https://console.groq.com" target="_blank" rel="noopener noreferrer" className="text-blue-400 hover:text-blue-300 underline">console.groq.com</a></li>
            <li>Sign up or log in to your account</li>
            <li>Navigate to API Keys section</li>
            <li>Create a new API key</li>
            <li>Copy and paste it above</li>
          </ol>
          <p className="mt-4">
            <strong className="text-slate-300">Troubleshooting:</strong>
          </p>
          <ul className="list-disc list-inside space-y-1 ml-2">
            <li>Make sure your API key starts with "gsk_"</li>
            <li>Check that your Groq account has available credits</li>
            <li>Verify the backend server is running on port 8000</li>
            <li>Try the "Test Connection" button before saving</li>
          </ul>
        </div>
      </div>
    </div>
  );
}

// Made with Bob
