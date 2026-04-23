import { useMemo, useState, type ReactNode } from 'react';
import { AlertTriangle, ArrowRight, BadgeCheck, FileDown, FileText, Loader2, UploadCloud } from 'lucide-react';
import { Bar, BarChart, CartesianGrid, Cell, Legend, Pie, PieChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import {
  computeTax,
  extractDocument,
  generateItr,
  runPipeline,
  validateDocument,
  uploadDocument,
  type EntitySpan,
  type ExtractionResult,
  type ItrResult,
  type Regime,
  type TaxResult,
  type ValidationIssue,
  type ValidationResult,
} from './lib/api';

type FieldRow = {
  label: string;
  value: string;
  confidence: number;
  source: string;
};

const initialFields: FieldRow[] = [
  { label: 'PAN', value: 'ABCDE1234F', confidence: 0.98, source: 'regex' },
  { label: 'EmployerName', value: 'Acme Consulting Pvt Ltd', confidence: 0.86, source: 'heuristic' },
  { label: 'EmployeeName', value: 'Aarav Sharma', confidence: 0.84, source: 'heuristic' },
  { label: 'GrossIncome', value: '1250000', confidence: 0.91, source: 'heuristic' },
  { label: 'Section80C', value: '150000', confidence: 0.88, source: 'heuristic' },
  { label: 'Section80D', value: '25000', confidence: 0.84, source: 'heuristic' },
  { label: 'TDS', value: '84500', confidence: 0.9, source: 'regex' },
];

const statusPills = ['Upload', 'OCR', 'NER', 'Validate', 'Compute', 'Generate'];

const warningColors: Record<ValidationIssue['severity'], string> = {
  high: 'border-red-300 bg-red-50 text-red-700',
  medium: 'border-amber-300 bg-amber-50 text-amber-800',
  low: 'border-slate-200 bg-slate-50 text-slate-700',
};

export default function App() {
  const [documentId, setDocumentId] = useState<number | null>(null);
  const [fileName, setFileName] = useState('No file uploaded');
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState('Ready to ingest Form 16 and Form 26AS documents.');
  const [fields, setFields] = useState<FieldRow[]>(initialFields);
  const [extraction, setExtraction] = useState<ExtractionResult | null>(null);
  const [validation, setValidation] = useState<ValidationResult | null>(null);
  const [tax, setTax] = useState<TaxResult | null>(null);
  const [itr, setItr] = useState<ItrResult | null>(null);
  const [selectedRegime, setSelectedRegime] = useState<Regime>('new');

  const dashboardCards = useMemo(() => {
    const confidence = extraction?.confidence ?? fields.reduce((total, field) => total + field.confidence, 0) / Math.max(fields.length, 1);
    return [
      { label: 'Document ID', value: documentId ? `#${documentId}` : 'Pending' },
      { label: 'OCR Confidence', value: `${Math.round(confidence * 100)}%` },
      { label: 'Validation', value: validation?.is_valid ? 'Clean' : validation ? `${validation.issues.length} issues` : 'Pending' },
      { label: 'Tax Liability', value: tax ? `₹${tax.tax_liability.toLocaleString('en-IN')}` : 'Pending' },
    ];
  }, [documentId, extraction?.confidence, fields, tax, validation]);

  const chartData = useMemo(() => {
    const gross = tax?.gross_income ?? 0;
    const deductions = tax?.total_deductions ?? 0;
    const taxLiability = tax?.tax_liability ?? 0;
    return [
      { name: 'Income', value: gross },
      { name: 'Deductions', value: deductions },
      { name: 'Tax', value: taxLiability },
    ];
  }, [tax]);

  async function handleUpload(file: File | null) {
    if (!file) return;
    setLoading(true);
    setMessage('Uploading document and initializing pipeline...');
    setFileName(file.name);
    try {
      const uploaded = await uploadDocument(file, file.name.toLowerCase().includes('26') ? 'form26as' : 'form16');
      setDocumentId(uploaded.document_id);
      setMessage(`Uploaded ${uploaded.filename}. You can run extraction or the full pipeline.`);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : 'Upload failed');
    } finally {
      setLoading(false);
    }
  }

  function updateField(index: number, key: keyof FieldRow, value: string) {
    setFields((current) => current.map((field, fieldIndex) => (fieldIndex === index ? { ...field, [key]: key === 'confidence' ? Number(value) : value } : field)));
  }

  async function handleExtraction() {
    if (!documentId) return;
    setLoading(true);
    setMessage('Running OCR and entity extraction...');
    try {
      const extracted = await extractDocument(documentId);
      setExtraction(extracted);
      setFields(extracted.entities.map((entity) => ({ label: entity.label, value: entity.value, confidence: entity.confidence, source: entity.source })));
      setMessage(`Extraction complete with ${Math.round(extracted.confidence * 100)}% confidence.`);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : 'Extraction failed');
    } finally {
      setLoading(false);
    }
  }

  async function handleValidation() {
    if (!documentId) return;
    setLoading(true);
    setMessage('Validating cross-document fields...');
    try {
      const form16 = fields.reduce<Record<string, unknown>>((accumulator, field) => ({ ...accumulator, [field.label]: field.value }), {});
      const form26as = {
        PAN: fields.find((field) => field.label === 'PAN')?.value ?? 'ABCDE1234F',
        TAN: 'MUMA12345B',
        TDS: 84000,
        GrossIncome: 1248000,
      };
      const result = await validateDocument(documentId, form16, form26as);
      setValidation(result);
      setMessage(result.is_valid ? 'Validation passed.' : `Validation found ${result.issues.length} issues.`);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : 'Validation failed');
    } finally {
      setLoading(false);
    }
  }

  async function handleComputeTax() {
    if (!documentId) return;
    setLoading(true);
    setMessage('Computing tax under selected regime...');
    try {
      const result = await computeTax(documentId, {
        regime: selectedRegime,
        gross_income: Number(fields.find((field) => field.label === 'GrossIncome')?.value ?? 0),
        deductions_80c: Number(fields.find((field) => field.label === 'Section80C')?.value ?? 0),
        deductions_80d: Number(fields.find((field) => field.label === 'Section80D')?.value ?? 0),
        tds: Number(fields.find((field) => field.label === 'TDS')?.value ?? 0),
      });
      setTax(result);
      setMessage(`Tax computed: ₹${result.tax_liability.toLocaleString('en-IN')}.`);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : 'Tax computation failed');
    } finally {
      setLoading(false);
    }
  }

  async function handleGenerate() {
    if (!documentId) return;
    setLoading(true);
    setMessage('Generating ITR JSON/XML/PDF outputs...');
    try {
      const payload = {
        form16: fields.reduce<Record<string, unknown>>((accumulator, field) => ({ ...accumulator, [field.label]: field.value }), {}),
        form26as: {
          PAN: fields.find((field) => field.label === 'PAN')?.value ?? 'ABCDE1234F',
          TAN: 'MUMA12345B',
          TDS: Number(fields.find((field) => field.label === 'TDS')?.value ?? 0),
          GrossIncome: Number(fields.find((field) => field.label === 'GrossIncome')?.value ?? 0),
        },
        tax_request: {
          regime: selectedRegime,
          gross_income: Number(fields.find((field) => field.label === 'GrossIncome')?.value ?? 0),
          deductions_80c: Number(fields.find((field) => field.label === 'Section80C')?.value ?? 0),
          deductions_80d: Number(fields.find((field) => field.label === 'Section80D')?.value ?? 0),
          tds: Number(fields.find((field) => field.label === 'TDS')?.value ?? 0),
        },
      };
      const result = await generateItr(documentId, payload);
      setItr(result);
      setMessage('ITR package generated successfully.');
    } catch (error) {
      setMessage(error instanceof Error ? error.message : 'ITR generation failed');
    } finally {
      setLoading(false);
    }
  }

  async function handleRunAll() {
    if (!documentId) return;
    setLoading(true);
    setMessage('Running full end-to-end workflow...');
    try {
      const payload = {
        form16: fields.reduce<Record<string, unknown>>((accumulator, field) => ({ ...accumulator, [field.label]: field.value }), {}),
        form26as: {
          PAN: fields.find((field) => field.label === 'PAN')?.value ?? 'ABCDE1234F',
          TAN: 'MUMA12345B',
          TDS: Number(fields.find((field) => field.label === 'TDS')?.value ?? 0),
          GrossIncome: Number(fields.find((field) => field.label === 'GrossIncome')?.value ?? 0),
        },
        tax_request: {
          regime: selectedRegime,
          gross_income: Number(fields.find((field) => field.label === 'GrossIncome')?.value ?? 0),
          deductions_80c: Number(fields.find((field) => field.label === 'Section80C')?.value ?? 0),
          deductions_80d: Number(fields.find((field) => field.label === 'Section80D')?.value ?? 0),
          tds: Number(fields.find((field) => field.label === 'TDS')?.value ?? 0),
        },
      };
      const response = await runPipeline(documentId, payload);
      const pipeline = response as {
        extraction?: ExtractionResult;
        validation?: ValidationResult;
        tax?: TaxResult;
        itr?: ItrResult;
      };
      if (pipeline.extraction) setExtraction(pipeline.extraction);
      if (pipeline.validation) setValidation(pipeline.validation);
      if (pipeline.tax) setTax(pipeline.tax);
      if (pipeline.itr) setItr(pipeline.itr);
      setMessage('End-to-end workflow completed.');
    } catch (error) {
      setMessage(error instanceof Error ? error.message : 'Pipeline failed');
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen bg-dashboard-glow text-ink">
      <div className="mx-auto flex max-w-7xl flex-col gap-8 px-4 py-6 lg:px-8">
        <header className="grid gap-4 rounded-3xl border border-white/70 bg-white/70 p-6 shadow-panel backdrop-blur xl:grid-cols-[1.2fr_0.8fr]">
          <div>
            <p className="mb-3 inline-flex rounded-full border border-sand-200 bg-sand-50 px-3 py-1 text-xs font-semibold uppercase tracking-[0.24em] text-sand-700">
              Hybrid AI workflow for India tax filing
            </p>
            <h1 className="max-w-3xl text-4xl font-semibold leading-tight text-ink md:text-5xl">
              Automated tax return filing with OCR, NER, validation, and explainable tax computation.
            </h1>
            <p className="mt-4 max-w-2xl text-sm leading-6 text-slate">
              Upload Form 16 and Form 26AS, inspect extracted fields, resolve mismatches, and generate ITR-ready outputs with a reproducible audit trail.
            </p>
          </div>
          <div className="grid gap-3 rounded-2xl border border-sand-100 bg-sand-50 p-4">
            <div className="flex items-center justify-between text-sm font-medium text-sand-800">
              <span>Workflow health</span>
              <span className="inline-flex items-center gap-2 rounded-full bg-white px-3 py-1 text-teal shadow-sm">
                <BadgeCheck size={14} />
                Production-ready
              </span>
            </div>
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 xl:grid-cols-6">
              {statusPills.map((pill, index) => (
                <div key={pill} className="rounded-2xl border border-white bg-white/90 px-3 py-2 text-center text-xs font-semibold text-slate shadow-sm">
                  <span className="block text-[10px] uppercase tracking-[0.18em] text-sand-600">Step {index + 1}</span>
                  {pill}
                </div>
              ))}
            </div>
            <div className="rounded-2xl border border-white/70 bg-white p-4 text-sm text-slate shadow-sm">{message}</div>
          </div>
        </header>

        <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
          {dashboardCards.map((card) => (
            <article key={card.label} className="rounded-3xl border border-white/70 bg-white/80 p-5 shadow-panel backdrop-blur">
              <p className="text-xs font-semibold uppercase tracking-[0.24em] text-sand-600">{card.label}</p>
              <p className="mt-2 text-3xl font-semibold text-ink">{card.value}</p>
            </article>
          ))}
        </section>

        <section className="grid gap-6 xl:grid-cols-[0.92fr_1.08fr]">
          <article className="rounded-3xl border border-white/70 bg-white/85 p-6 shadow-panel backdrop-blur">
            <div className="flex items-center justify-between gap-3">
              <div>
                <h2 className="text-xl font-semibold text-ink">Document control center</h2>
                <p className="mt-1 text-sm text-slate">Upload, preprocess, extract, validate, and generate outputs from one workflow.</p>
              </div>
              {loading ? <Loader2 className="animate-spin text-sand-600" /> : <FileText className="text-sand-600" />}
            </div>

            <label className="mt-5 flex cursor-pointer flex-col items-center justify-center gap-3 rounded-3xl border-2 border-dashed border-sand-200 bg-sand-50 px-4 py-10 text-center transition hover:border-sand-400 hover:bg-sand-100">
              <UploadCloud size={30} className="text-sand-600" />
              <span className="text-base font-semibold text-ink">Drop a PDF or scan here</span>
              <span className="text-sm text-slate">Form 16, Form 26AS, salary statements, investment proofs</span>
              <input className="hidden" type="file" accept="application/pdf,image/*" onChange={(event) => handleUpload(event.target.files?.[0] ?? null)} />
            </label>

            <div className="mt-4 flex flex-wrap gap-3 text-sm text-slate">
              <span className="rounded-full border border-sand-200 bg-white px-3 py-1">{fileName}</span>
              {documentId ? <span className="rounded-full border border-teal-200 bg-teal-50 px-3 py-1 text-teal">Document #{documentId}</span> : null}
            </div>

            <div className="mt-5 grid grid-cols-2 gap-3 lg:grid-cols-3">
              <ActionButton label="Extract" icon={<ArrowRight size={16} />} onClick={handleExtraction} disabled={!documentId || loading} />
              <ActionButton label="Validate" icon={<AlertTriangle size={16} />} onClick={handleValidation} disabled={!documentId || loading} />
              <ActionButton label="Compute tax" icon={<BadgeCheck size={16} />} onClick={handleComputeTax} disabled={!documentId || loading} />
              <ActionButton label="Generate ITR" icon={<FileDown size={16} />} onClick={handleGenerate} disabled={!documentId || loading} />
              <ActionButton label="Run all" icon={<ArrowRight size={16} />} onClick={handleRunAll} disabled={!documentId || loading} className="col-span-2 lg:col-span-1" />
            </div>

            <div className="mt-5 flex items-center gap-3 rounded-2xl border border-sand-100 bg-white p-4 text-sm">
              <span className="font-semibold text-slate">Regime</span>
              <div className="flex rounded-full border border-sand-200 bg-sand-50 p-1">
                {(['new', 'old'] as Regime[]).map((regime) => (
                  <button
                    key={regime}
                    className={`rounded-full px-4 py-1.5 text-xs font-semibold uppercase tracking-[0.18em] transition ${selectedRegime === regime ? 'bg-ink text-white' : 'text-slate'}`}
                    onClick={() => setSelectedRegime(regime)}
                  >
                    {regime}
                  </button>
                ))}
              </div>
            </div>

            <div className="mt-6 overflow-hidden rounded-3xl border border-sand-100 bg-white">
              <div className="flex items-center justify-between border-b border-sand-100 px-4 py-3">
                <h3 className="font-semibold text-ink">Editable extracted fields</h3>
                <span className="text-xs text-slate">Confidence-aware and user editable</span>
              </div>
              <div className="overflow-x-auto">
                <table className="min-w-full divide-y divide-sand-100 text-sm">
                  <thead className="bg-sand-50 text-left text-xs uppercase tracking-[0.18em] text-sand-700">
                    <tr>
                      <th className="px-4 py-3">Field</th>
                      <th className="px-4 py-3">Value</th>
                      <th className="px-4 py-3">Confidence</th>
                      <th className="px-4 py-3">Source</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-sand-100">
                    {fields.map((field, index) => (
                      <tr key={`${field.label}-${index}`} className="align-top">
                        <td className="px-4 py-3 font-medium text-ink">{field.label}</td>
                        <td className="px-4 py-3">
                          <input
                            value={field.value}
                            onChange={(event) => updateField(index, 'value', event.target.value)}
                            className="w-full rounded-xl border border-sand-200 bg-sand-50 px-3 py-2 text-sm outline-none ring-0 transition focus:border-sand-400"
                          />
                        </td>
                        <td className="px-4 py-3">
                          <input
                            type="number"
                            min="0"
                            max="1"
                            step="0.01"
                            value={field.confidence}
                            onChange={(event) => updateField(index, 'confidence', event.target.value)}
                            className="w-24 rounded-xl border border-sand-200 bg-sand-50 px-3 py-2 text-sm outline-none focus:border-sand-400"
                          />
                        </td>
                        <td className="px-4 py-3 text-slate">{field.source}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </article>

          <div className="grid gap-6">
            <article className="rounded-3xl border border-white/70 bg-white/85 p-6 shadow-panel backdrop-blur">
              <div className="flex items-center justify-between">
                <div>
                  <h2 className="text-xl font-semibold text-ink">Tax summary</h2>
                  <p className="mt-1 text-sm text-slate">Explainable breakdown with regime-aware liability and refund state.</p>
                </div>
                <div className="rounded-full border border-sand-200 bg-sand-50 px-3 py-1 text-xs font-semibold uppercase tracking-[0.18em] text-sand-700">
                  {selectedRegime} regime
                </div>
              </div>
              <div className="mt-5 grid gap-4 md:grid-cols-2">
                <div className="rounded-2xl bg-ink p-5 text-white">
                  <p className="text-sm text-white/70">Tax liability</p>
                  <p className="mt-2 text-4xl font-semibold">{tax ? `₹${tax.tax_liability.toLocaleString('en-IN')}` : 'Pending'}</p>
                  <p className="mt-2 text-sm text-white/70">Refund/payable: {tax ? `₹${tax.refund_payable.toLocaleString('en-IN')}` : 'Pending'}</p>
                </div>
                <div className="rounded-2xl border border-sand-100 bg-sand-50 p-5">
                  <p className="text-sm font-semibold uppercase tracking-[0.18em] text-sand-700">Explainability</p>
                  <ul className="mt-3 space-y-2 text-sm text-slate">
                    {(tax?.assumptions ?? ['Waiting for computation.']).map((item) => (
                      <li key={item} className="flex gap-2">
                        <span className="mt-1 h-2 w-2 rounded-full bg-sand-500" />
                        <span>{item}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              </div>
              <div className="mt-5 h-72 rounded-2xl border border-sand-100 bg-white p-2">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={chartData}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#eadfce" />
                    <XAxis dataKey="name" />
                    <YAxis />
                    <Tooltip />
                    <Legend />
                    <Bar dataKey="value" radius={[12, 12, 0, 0]} fill="#bc8422" />
                  </BarChart>
                </ResponsiveContainer>
              </div>
              {tax?.breakdown?.length ? (
                <div className="mt-4 flex h-56 items-center justify-center rounded-2xl border border-sand-100 bg-white">
                  <ResponsiveContainer width="100%" height="100%">
                    <PieChart>
                      <Pie data={chartData} dataKey="value" nameKey="name" innerRadius={60} outerRadius={90} paddingAngle={4}>
                        {chartData.map((entry, index) => (
                          <Cell key={entry.name} fill={['#bc8422', '#0f766e', '#f04438'][index % 3]} />
                        ))}
                      </Pie>
                      <Tooltip />
                      <Legend />
                    </PieChart>
                  </ResponsiveContainer>
                </div>
              ) : null}
            </article>

            <article className="rounded-3xl border border-white/70 bg-white/85 p-6 shadow-panel backdrop-blur">
              <h2 className="text-xl font-semibold text-ink">Validation report</h2>
              <p className="mt-1 text-sm text-slate">PAN/TAN reconciliation, TDS matching, and cross-document consistency checks.</p>
              <div className="mt-5 space-y-3">
                {(validation?.issues.length ? validation.issues : [{ severity: 'low', field: 'status', message: 'No validation issues yet.', source_documents: [] } as ValidationIssue]).map((issue) => (
                  <div key={`${issue.field}-${issue.message}`} className={`rounded-2xl border p-4 text-sm ${warningColors[issue.severity] ?? warningColors.low}`}>
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <strong>{issue.field}</strong>
                      <span className="text-xs uppercase tracking-[0.18em]">{issue.severity}</span>
                    </div>
                    <p className="mt-2">{issue.message}</p>
                    {issue.expected || issue.observed ? (
                      <p className="mt-2 text-xs opacity-80">
                        Expected: {issue.expected ?? 'n/a'} | Observed: {issue.observed ?? 'n/a'}
                      </p>
                    ) : null}
                  </div>
                ))}
              </div>
            </article>

            <article className="rounded-3xl border border-white/70 bg-white/85 p-6 shadow-panel backdrop-blur">
              <h2 className="text-xl font-semibold text-ink">Output artifacts</h2>
              <div className="mt-4 grid gap-3 sm:grid-cols-3">
                <ArtifactCard label="ITR JSON" value={itr?.json_path ?? 'Pending'} />
                <ArtifactCard label="ITR XML" value={itr?.xml_path ?? 'Pending'} />
                <ArtifactCard label="Summary PDF" value={itr?.report_path ?? 'Pending'} />
              </div>
              <p className="mt-4 text-sm text-slate">Use these artifacts for handoff into downstream filing systems or compliance review.</p>
            </article>
          </div>
        </section>
      </div>
    </div>
  );
}

function ActionButton({ label, icon, onClick, disabled, className = '' }: { label: string; icon: ReactNode; onClick: () => void; disabled?: boolean; className?: string }) {
  return (
    <button
      onClick={onClick}
      disabled={disabled}
      className={`inline-flex items-center justify-center gap-2 rounded-2xl border border-sand-200 bg-ink px-4 py-3 text-sm font-semibold text-white transition hover:-translate-y-0.5 hover:shadow-lg disabled:cursor-not-allowed disabled:opacity-50 ${className}`}
    >
      {icon}
      {label}
    </button>
  );
}

function ArtifactCard({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-2xl border border-sand-100 bg-sand-50 p-4">
      <p className="text-xs font-semibold uppercase tracking-[0.18em] text-sand-700">{label}</p>
      <p className="mt-2 break-all text-sm text-ink">{value}</p>
    </div>
  );
}
