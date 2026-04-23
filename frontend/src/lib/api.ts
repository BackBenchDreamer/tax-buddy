export type Regime = 'old' | 'new';

export type EntitySpan = {
  label: string;
  value: string;
  confidence: number;
  source: string;
  page?: number | null;
  bbox?: number[] | null;
};

export type ExtractionResult = {
  document_id: number;
  text: string;
  normalized_text: string;
  confidence: number;
  entities: EntitySpan[];
  layout_metadata: Record<string, unknown>;
};

export type ValidationIssue = {
  severity: 'low' | 'medium' | 'high';
  field: string;
  message: string;
  expected?: string | null;
  observed?: string | null;
  source_documents: string[];
};

export type ValidationResult = {
  is_valid: boolean;
  issues: ValidationIssue[];
  reconciled_fields: Record<string, unknown>;
};

export type TaxBreakdownItem = {
  label: string;
  amount: number;
  explanation: string;
};

export type TaxResult = {
  regime: Regime;
  gross_income: number;
  total_deductions: number;
  taxable_income: number;
  tax_liability: number;
  cess: number;
  refund_payable: number;
  breakdown: TaxBreakdownItem[];
  assumptions: string[];
};

export type ItrResult = {
  document_id: number;
  json_path: string;
  xml_path: string;
  report_path: string;
  payload: Record<string, unknown>;
};

const apiBase = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000/api';

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${apiBase}${path}`, init);
  if (!response.ok) {
    const detail = await response.text();
    throw new Error(detail || `Request failed with ${response.status}`);
  }
  return response.json() as Promise<T>;
}

export async function uploadDocument(file: File, documentType = 'unknown') {
  const formData = new FormData();
  formData.append('file', file);
  formData.append('document_type', documentType);
  return request<{ document_id: number; filename: string; document_type: string; storage_path: string }>('/upload', {
    method: 'POST',
    body: formData,
  });
}

export async function extractDocument(documentId: number) {
  return request<ExtractionResult>(`/extract/${documentId}`, { method: 'POST' });
}

export async function validateDocument(documentId: number, form16: Record<string, unknown>, form26as: Record<string, unknown>) {
  return request<ValidationResult>(`/validate/${documentId}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ form16, form26as }),
  });
}

export async function computeTax(documentId: number, payload: Record<string, unknown>) {
  return request<TaxResult>(`/compute-tax/${documentId}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
}

export async function generateItr(documentId: number, payload: Record<string, unknown>) {
  return request<ItrResult>(`/generate-itr/${documentId}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
}

export async function runPipeline(documentId: number, payload: Record<string, unknown>) {
  return request<Record<string, unknown>>(`/pipeline/${documentId}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
}
