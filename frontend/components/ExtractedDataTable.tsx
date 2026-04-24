'use client';

import { useState } from 'react';
import { Entity, ExtractedData } from '@/types';
import { formatCurrency, cn } from '@/lib/utils';
import { User, Wallet, Receipt, ChevronDown, FileText } from 'lucide-react';

interface ExtractedDataTableProps {
  entities: Entity[];
}

const PERSONAL_FIELDS: Array<{ key: keyof ExtractedData; label: string }> = [
  { key: 'PAN', label: 'PAN' },
  { key: 'TAN', label: 'TAN (Employer)' },
  { key: 'AssessmentYear', label: 'Assessment Year' },
  { key: 'EmployerName', label: 'Employer' },
  { key: 'EmployeeName', label: 'Employee' },
];

const INCOME_FIELDS: Array<{ key: keyof ExtractedData; label: string; isCurrency: boolean }> = [
  { key: 'GrossSalary', label: 'Gross Salary', isCurrency: true },
  { key: 'TaxableIncome', label: 'Taxable Income', isCurrency: true },
  { key: 'TDS', label: 'TDS Deducted', isCurrency: true },
];

const DEDUCTION_FIELDS: Array<{ key: keyof ExtractedData; label: string }> = [
  { key: 'Section80C', label: 'Section 80C' },
  { key: 'Section80D', label: 'Section 80D' },
];

export function ExtractedDataTable({ entities }: ExtractedDataTableProps) {
  const map: Record<string, string> = {};
  entities.forEach((e) => { map[e.label] = e.value; });

  const get = (key: string): string | undefined => map[key];
  const getNum = (key: string): number | undefined => {
    const v = map[key];
    return v != null ? parseFloat(v) : undefined;
  };

  const avgConf = entities.length > 0
    ? entities.reduce((s, e) => s + e.confidence, 0) / entities.length
    : 0;

  return (
    <div className="glow-card p-5 flex flex-col gap-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <div className="w-7 h-7 rounded-lg bg-violet-500/20 flex items-center justify-center">
            <FileText className="w-4 h-4 text-violet-400" />
          </div>
          <h2 className="text-sm font-semibold text-slate-200 tracking-wide uppercase">Extracted Data</h2>
        </div>
        <span className="text-xs text-slate-500 bg-slate-800 px-2 py-0.5 rounded-full">
          {entities.length} fields · {(avgConf * 100).toFixed(0)}% conf
        </span>
      </div>

      {/* Accordion sections */}
      <div className="flex flex-col gap-2">
        <AccordionSection
          icon={<User className="w-3.5 h-3.5" />}
          title="Personal Info"
          color="violet"
          defaultOpen={false}
          count={PERSONAL_FIELDS.filter(f => get(String(f.key))).length}
        >
          {PERSONAL_FIELDS.map(({ key, label }) => (
            <Row key={String(key)} label={label} value={get(String(key))} mono={['PAN','TAN'].includes(String(key))} />
          ))}
        </AccordionSection>

        <AccordionSection
          icon={<Wallet className="w-3.5 h-3.5" />}
          title="Income"
          color="indigo"
          defaultOpen={true}
          count={INCOME_FIELDS.filter(f => getNum(String(f.key)) != null).length}
        >
          {INCOME_FIELDS.map(({ key, label, isCurrency }) => {
            const val = getNum(String(key));
            return (
              <Row
                key={String(key)}
                label={label}
                value={isCurrency && val != null ? formatCurrency(val) : val?.toString()}
                highlight={label === 'TDS Deducted'}
              />
            );
          })}
        </AccordionSection>

        <AccordionSection
          icon={<Receipt className="w-3.5 h-3.5" />}
          title="Deductions"
          color="emerald"
          defaultOpen={false}
          count={DEDUCTION_FIELDS.filter(f => getNum(String(f.key)) != null).length}
        >
          {DEDUCTION_FIELDS.map(({ key, label }) => {
            const val = getNum(String(key));
            return <Row key={String(key)} label={label} value={val != null ? formatCurrency(val) : undefined} />;
          })}
        </AccordionSection>
      </div>
    </div>
  );
}

// ── Accordion Section ────────────────────────────────────────────────────

function AccordionSection({
  icon, title, color, children, defaultOpen = false, count,
}: {
  icon: React.ReactNode;
  title: string;
  color: 'violet' | 'indigo' | 'emerald';
  children: React.ReactNode;
  defaultOpen?: boolean;
  count: number;
}) {
  const [open, setOpen] = useState(defaultOpen);

  const colorMap = {
    violet: 'text-violet-400 bg-violet-500/10',
    indigo: 'text-indigo-400 bg-indigo-500/10',
    emerald: 'text-emerald-400 bg-emerald-500/10',
  };

  return (
    <div className="rounded-xl bg-slate-900/40 border border-slate-800/60 overflow-hidden">
      <button
        onClick={() => setOpen(!open)}
        className={cn(
          'w-full flex items-center justify-between px-4 py-2.5 transition-colors hover:bg-slate-800/20',
          colorMap[color],
        )}
      >
        <div className="flex items-center gap-2">
          {icon}
          <span className="text-xs font-semibold uppercase tracking-widest">{title}</span>
          <span className="text-[10px] opacity-50 ml-1">({count})</span>
        </div>
        <ChevronDown className={cn('w-3.5 h-3.5 opacity-60 transition-transform duration-200', open && 'rotate-180')} />
      </button>
      <div className={cn(
        'transition-all duration-200 ease-in-out overflow-hidden',
        open ? 'max-h-[500px] opacity-100' : 'max-h-0 opacity-0',
      )}>
        <div className="divide-y divide-slate-800/40">{children}</div>
      </div>
    </div>
  );
}

// ── Row ──────────────────────────────────────────────────────────────────

function Row({
  label, value, mono = false, highlight = false,
}: {
  label: string;
  value?: string;
  mono?: boolean;
  highlight?: boolean;
}) {
  return (
    <div className="flex items-center justify-between px-4 py-2.5 group">
      <span className="text-xs text-slate-500 group-hover:text-slate-400 transition-colors">{label}</span>
      <span
        className={cn('text-xs font-medium', {
          'text-slate-700 italic': !value,
          'text-amber-400': highlight && value,
          'font-mono text-slate-200 tracking-wider': mono && value && !highlight,
          'text-slate-200': value && !highlight && !mono,
        })}
      >
        {value ?? 'Not detected'}
      </span>
    </div>
  );
}
