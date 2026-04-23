'use client';

import { ValidationResult, ValidationIssue } from '@/types';
import { ShieldCheck, ShieldAlert, ShieldX, AlertTriangle, CheckCircle2, XCircle } from 'lucide-react';
import { cn, getSeverityColor } from '@/lib/utils';

interface ValidationPanelProps {
  result: ValidationResult;
}

export function ValidationPanel({ result }: ValidationPanelProps) {
  const { status, score, issues } = result;

  const statusConfig = {
    ok: { icon: ShieldCheck, label: 'Verified', ring: 'text-emerald-400', bg: 'bg-emerald-500/10', glow: '0 0 30px rgba(16,185,129,0.15)', track: '#10b981' },
    warning: { icon: ShieldAlert, label: 'Warnings', ring: 'text-amber-400', bg: 'bg-amber-500/10', glow: '0 0 30px rgba(245,158,11,0.15)', track: '#f59e0b' },
    error: { icon: ShieldX, label: 'Issues Found', ring: 'text-red-400', bg: 'bg-red-500/10', glow: '0 0 30px rgba(239,68,68,0.15)', track: '#ef4444' },
  }[status] ?? { icon: ShieldCheck, label: 'Unknown', ring: 'text-slate-400', bg: 'bg-slate-500/10', glow: 'none', track: '#6b7280' };

  const Icon = statusConfig.icon;
  const circumference = 2 * Math.PI * 36;
  const dashOffset = circumference - (score / 100) * circumference;

  return (
    <div className="glow-card p-5 flex flex-col gap-5 h-full">
      <div className="flex items-center gap-2">
        <div className={cn('w-7 h-7 rounded-lg flex items-center justify-center', statusConfig.bg)}>
          <Icon className={cn('w-4 h-4', statusConfig.ring)} />
        </div>
        <h2 className="text-sm font-semibold text-slate-200 tracking-wide uppercase">Validation</h2>
      </div>

      <div className="flex flex-col items-center gap-3 py-2">
        <div className="relative" style={{ filter: `drop-shadow(${statusConfig.glow})` }}>
          <svg width="100" height="100" className="-rotate-90">
            <circle cx="50" cy="50" r="36" fill="none" stroke="#1e2130" strokeWidth="8" />
            <circle
              cx="50" cy="50" r="36" fill="none"
              stroke={statusConfig.track}
              strokeWidth="8"
              strokeLinecap="round"
              strokeDasharray={circumference}
              strokeDashoffset={dashOffset}
              className="transition-all duration-700 ease-out"
            />
          </svg>
          <div className="absolute inset-0 flex flex-col items-center justify-center">
            <span className="text-2xl font-bold text-slate-100">{score}</span>
            <span className="text-[10px] text-slate-500 uppercase tracking-widest">Trust</span>
          </div>
        </div>
        <div className={cn('flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold', statusConfig.bg)}>
          <span className={statusConfig.ring}>{statusConfig.label}</span>
        </div>
      </div>

      <div className="grid grid-cols-3 gap-2">
        {[
          { label: 'Score', value: `${score}/100`, color: 'text-slate-200' },
          { label: 'Issues', value: issues.length === 0 ? 'None' : `${issues.length}`, color: issues.length === 0 ? 'text-emerald-400' : 'text-amber-400' },
          { label: 'Status', value: status.toUpperCase(), color: statusConfig.ring },
        ].map(({ label, value, color }) => (
          <div key={label} className="bg-slate-900/40 border border-slate-800/60 rounded-xl p-3 text-center">
            <div className={`text-sm font-semibold ${color}`}>{value}</div>
            <div className="text-[10px] text-slate-600 mt-0.5 uppercase tracking-wider">{label}</div>
          </div>
        ))}
      </div>

      <div className="flex flex-col gap-2 flex-1 overflow-auto">
        {issues.length === 0 ? (
          <div className="flex flex-col items-center gap-2 py-6 text-center">
            <CheckCircle2 className="w-8 h-8 text-emerald-400" />
            <p className="text-sm font-medium text-slate-300">All checks passed</p>
            <p className="text-xs text-slate-600">No discrepancies found</p>
          </div>
        ) : (
          issues.map((issue, i) => <IssueCard key={i} issue={issue} />)
        )}
      </div>
    </div>
  );
}

function IssueCard({ issue }: { issue: ValidationIssue }) {
  const colorClass = getSeverityColor(issue.severity);
  const SevIcon = issue.severity.toLowerCase().includes('high') ? XCircle : AlertTriangle;
  return (
    <div className={cn('rounded-xl border p-3 flex gap-3', colorClass)}>
      <SevIcon className="w-4 h-4 mt-0.5 shrink-0" />
      <div className="flex-1 min-w-0">
        <div className="flex items-center justify-between gap-2 mb-0.5">
          <span className="text-xs font-semibold truncate">{issue.type.replace(/_/g, ' ')}</span>
          <span className="text-[10px] opacity-70 uppercase tracking-wider shrink-0">{issue.severity}</span>
        </div>
        <p className="text-xs opacity-80 leading-relaxed">{issue.message}</p>
      </div>
    </div>
  );
}
