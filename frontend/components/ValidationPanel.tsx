'use client';

import { useState } from 'react';
import { ValidationResult, ValidationIssue } from '@/types';
import { ShieldCheck, ShieldAlert, ShieldX, AlertTriangle, CheckCircle2, XCircle, ChevronDown, ChevronUp } from 'lucide-react';
import { cn, getSeverityColor } from '@/lib/utils';

interface ValidationPanelProps {
  result: ValidationResult;
}

export function ValidationPanel({ result }: ValidationPanelProps) {
  const [showIssues, setShowIssues] = useState(false);
  const { status, score, issues } = result;

  const statusConfig = {
    ok: { icon: ShieldCheck, label: 'Verified', ring: 'text-emerald-400', bg: 'bg-emerald-500/10', glow: '0 0 24px rgba(16,185,129,0.15)', track: '#10b981' },
    warning: { icon: ShieldAlert, label: 'Warnings', ring: 'text-amber-400', bg: 'bg-amber-500/10', glow: '0 0 24px rgba(245,158,11,0.15)', track: '#f59e0b' },
    error: { icon: ShieldX, label: 'Issues Found', ring: 'text-red-400', bg: 'bg-red-500/10', glow: '0 0 24px rgba(239,68,68,0.15)', track: '#ef4444' },
  }[status] ?? { icon: ShieldCheck, label: 'Unknown', ring: 'text-slate-400', bg: 'bg-slate-500/10', glow: 'none', track: '#6b7280' };

  const Icon = statusConfig.icon;
  const circumference = 2 * Math.PI * 32;
  const dashOffset = circumference - (score / 100) * circumference;

  return (
    <div className="glow-card p-5 flex flex-col gap-4">
      {/* Header */}
      <div className="flex items-center gap-2">
        <div className={cn('w-7 h-7 rounded-lg flex items-center justify-center', statusConfig.bg)}>
          <Icon className={cn('w-4 h-4', statusConfig.ring)} />
        </div>
        <h2 className="text-sm font-semibold text-slate-200 tracking-wide uppercase">Validation</h2>
      </div>

      {/* Score ring + status — side by side for compactness */}
      <div className="flex items-center gap-5">
        <div className="relative shrink-0" style={{ filter: `drop-shadow(${statusConfig.glow})` }}>
          <svg width="80" height="80" className="-rotate-90">
            <circle cx="40" cy="40" r="32" fill="none" stroke="#1e2130" strokeWidth="7" />
            <circle
              cx="40" cy="40" r="32" fill="none"
              stroke={statusConfig.track}
              strokeWidth="7"
              strokeLinecap="round"
              strokeDasharray={circumference}
              strokeDashoffset={dashOffset}
              className="transition-all duration-700 ease-out"
            />
          </svg>
          <div className="absolute inset-0 flex flex-col items-center justify-center">
            <span className="text-xl font-bold text-slate-100">{score}</span>
            <span className="text-[9px] text-slate-500 uppercase tracking-widest">Trust</span>
          </div>
        </div>

        <div className="flex flex-col gap-2 flex-1">
          {/* Status badge */}
          <div className={cn('inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold w-fit', statusConfig.bg)}>
            <span className={statusConfig.ring}>{statusConfig.label}</span>
          </div>
          {/* Stats row */}
          <div className="flex gap-4">
            <div>
              <div className="text-sm font-semibold text-slate-200">{score}/100</div>
              <div className="text-[9px] text-slate-600 uppercase">Score</div>
            </div>
            <div>
              <div className={`text-sm font-semibold ${issues.length === 0 ? 'text-emerald-400' : 'text-amber-400'}`}>
                {issues.length === 0 ? 'None' : issues.length}
              </div>
              <div className="text-[9px] text-slate-600 uppercase">Issues</div>
            </div>
          </div>
        </div>
      </div>

      {/* All-clear or expandable issues */}
      {issues.length === 0 ? (
        <div className="flex items-center gap-2 px-3 py-2.5 rounded-xl bg-emerald-500/5 border border-emerald-500/15">
          <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0" />
          <p className="text-xs text-emerald-400/80">All checks passed — no discrepancies</p>
        </div>
      ) : (
        <div className="rounded-xl bg-slate-900/30 border border-slate-800/40 overflow-hidden">
          <button
            onClick={() => setShowIssues(!showIssues)}
            className="w-full flex items-center justify-between px-4 py-2.5 hover:bg-slate-800/20 transition-colors"
          >
            <span className="text-xs font-semibold text-amber-400">
              {issues.length} issue{issues.length > 1 ? 's' : ''} found
            </span>
            {showIssues ? <ChevronUp className="w-4 h-4 text-slate-500" /> : <ChevronDown className="w-4 h-4 text-slate-500" />}
          </button>
          {showIssues && (
            <div className="flex flex-col gap-2 p-3 pt-0 border-t border-slate-800/40">
              {issues.map((issue, i) => <IssueCard key={i} issue={issue} />)}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function IssueCard({ issue }: { issue: ValidationIssue }) {
  const colorClass = getSeverityColor(issue.severity);
  const SevIcon = issue.severity.toLowerCase().includes('high') ? XCircle : AlertTriangle;
  return (
    <div className={cn('rounded-lg border p-2.5 flex gap-2.5', colorClass)}>
      <SevIcon className="w-3.5 h-3.5 mt-0.5 shrink-0" />
      <div className="flex-1 min-w-0">
        <span className="text-[11px] font-semibold">{issue.type.replace(/_/g, ' ')}</span>
        <p className="text-[10px] opacity-70 leading-relaxed">{issue.message}</p>
      </div>
    </div>
  );
}
