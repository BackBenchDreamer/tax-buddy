# Tax Buddy Frontend

Modern, responsive React frontend for the Tax Buddy AI-powered tax filing system.

## Overview

The frontend is built with Next.js 14 (App Router), React 18, TypeScript, and Tailwind CSS. It provides an intuitive interface for uploading tax documents, viewing extracted data, validating information, and generating tax returns.

## Features

- **File Upload:** Drag-and-drop interface for Form 16 and Form 26AS
- **Real-time Processing:** Live updates during document processing
- **Data Visualization:** Interactive charts for tax breakdown and regime comparison
- **Validation Panel:** Clear display of validation issues with severity indicators
- **Tax Summary:** Comprehensive tax computation results
- **Responsive Design:** Works seamlessly on desktop, tablet, and mobile
- **Dark Mode Ready:** Prepared for dark mode implementation

## Tech Stack

- **Framework:** Next.js 14 (App Router)
- **UI Library:** React 18
- **Language:** TypeScript
- **Styling:** Tailwind CSS
- **Charts:** Recharts
- **HTTP Client:** Fetch API
- **Build Tool:** Next.js built-in (Turbopack)

## Getting Started

### Prerequisites

- Node.js 18 or higher
- npm, yarn, pnpm, or bun

### Installation

```bash
# Install dependencies
npm install

# Or with other package managers
yarn install
pnpm install
bun install
```

### Development

```bash
# Run development server
npm run dev

# Or with other package managers
yarn dev
pnpm dev
bun dev
```

Open [http://localhost:3000](http://localhost:3000) to view the application.

### Build

```bash
# Create production build
npm run build

# Start production server
npm start
```

### Linting

```bash
# Run ESLint
npm run lint
```

## Project Structure

```
frontend/
├── app/                    # Next.js App Router
│   ├── page.tsx           # Main application page
│   ├── layout.tsx         # Root layout with metadata
│   ├── globals.css        # Global styles and Tailwind
│   └── favicon.ico        # Application icon
├── components/            # React components
│   ├── FileUpload.tsx    # File upload component
│   ├── ProcessingSteps.tsx # Processing status display
│   ├── ExtractedDataTable.tsx # Data table component
│   ├── ValidationPanel.tsx # Validation results display
│   ├── TaxSummary.tsx    # Tax computation summary
│   ├── RegimeComparison.tsx # Old vs New regime comparison
│   ├── TaxExplanation.tsx # AI-powered explanations
│   └── Charts.tsx        # Tax breakdown charts
├── types/                 # TypeScript type definitions
│   └── index.ts          # Shared types and interfaces
├── public/               # Static assets
│   ├── file.svg
│   ├── globe.svg
│   ├── next.svg
│   ├── vercel.svg
│   └── window.svg
├── next.config.ts        # Next.js configuration
├── tsconfig.json         # TypeScript configuration
├── tailwind.config.ts    # Tailwind CSS configuration
├── postcss.config.mjs    # PostCSS configuration
├── eslint.config.mjs     # ESLint configuration
└── package.json          # Dependencies and scripts
```

## Components

### FileUpload

Handles file upload with drag-and-drop support.

```typescript
<FileUpload
  onUpload={handleFileUpload}
  accept=".pdf,image/*"
  maxSize={10 * 1024 * 1024}
/>
```

### ProcessingSteps

Displays the current processing status with step indicators.

```typescript
<ProcessingSteps
  currentStep={2}
  steps={['Upload', 'OCR', 'NER', 'Validation', 'Tax Computation']}
/>
```

### ExtractedDataTable

Shows extracted entities in a structured table format.

```typescript
<ExtractedDataTable
  entities={extractedData}
  onEdit={handleEdit}
/>
```

### ValidationPanel

Displays validation results with color-coded severity.

```typescript
<ValidationPanel
  validation={validationResult}
  onResolve={handleResolve}
/>
```

### TaxSummary

Shows comprehensive tax computation results.

```typescript
<TaxSummary
  taxData={taxResult}
  regime="old"
/>
```

### RegimeComparison

Compares Old and New tax regimes side-by-side.

```typescript
<RegimeComparison
  oldRegime={oldRegimeData}
  newRegime={newRegimeData}
/>
```

### Charts

Visualizes tax breakdown with interactive charts.

```typescript
<Charts
  data={taxBreakdown}
  type="bar"
/>
```

## API Integration

The frontend communicates with the backend API at `http://localhost:8000/api/v1`.

### Configuration

Update the API base URL in your components:

```typescript
const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1';
```

### Example API Call

```typescript
async function uploadFile(file: File) {
  const formData = new FormData();
  formData.append('file', file);

  const response = await fetch(`${API_BASE_URL}/upload`, {
    method: 'POST',
    body: formData,
  });

  if (!response.ok) {
    throw new Error('Upload failed');
  }

  return await response.json();
}
```

## Styling

### Tailwind CSS

The project uses Tailwind CSS for styling. Custom configurations are in `tailwind.config.ts`.

**Common Patterns:**

```tsx
// Card
<div className="bg-white rounded-lg shadow-md p-6">

// Button
<button className="bg-blue-600 hover:bg-blue-700 text-white font-semibold py-2 px-4 rounded">

// Input
<input className="border border-gray-300 rounded-md px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500">
```

### Global Styles

Global styles are defined in `app/globals.css`:

```css
@tailwind base;
@tailwind components;
@tailwind utilities;

/* Custom styles */
@layer components {
  .btn-primary {
    @apply bg-blue-600 hover:bg-blue-700 text-white font-semibold py-2 px-4 rounded;
  }
}
```

## TypeScript Types

Shared types are defined in `types/index.ts`:

```typescript
export interface Entity {
  label: string;
  value: string;
  confidence: number;
}

export interface ValidationResult {
  status: 'ok' | 'warning' | 'error';
  score: number;
  issues: ValidationIssue[];
}

export interface TaxResult {
  regime: 'old' | 'new';
  gross_income: number;
  taxable_income: number;
  total_tax: number;
  refund_or_payable: number;
  breakdown: TaxBreakdown[];
}
```

## Environment Variables

Create a `.env.local` file for local development:

```bash
NEXT_PUBLIC_API_URL=http://localhost:8000/api/v1
```

For production:

```bash
NEXT_PUBLIC_API_URL=https://api.yourdomain.com/api/v1
```

## Performance Optimization

- **Code Splitting:** Automatic with Next.js App Router
- **Image Optimization:** Use Next.js `<Image>` component
- **Lazy Loading:** Use React.lazy() for heavy components
- **Memoization:** Use React.memo() and useMemo() where appropriate

```typescript
import { memo } from 'react';

const ExpensiveComponent = memo(({ data }) => {
  // Component logic
});
```

## Testing

```bash
# Run tests (when configured)
npm test

# Run tests with coverage
npm test -- --coverage
```

## Deployment

### Vercel (Recommended)

1. Push code to GitHub
2. Import project in Vercel
3. Configure environment variables
4. Deploy

### Docker

```bash
# Build Docker image
docker build -t tax-buddy-frontend .

# Run container
docker run -p 3000:3000 tax-buddy-frontend
```

### Static Export

```bash
# Generate static export
npm run build
npm run export

# Deploy the 'out' directory to any static host
```

## Browser Support

- Chrome/Edge (latest)
- Firefox (latest)
- Safari (latest)
- Mobile browsers (iOS Safari, Chrome Mobile)

## Accessibility

- Semantic HTML
- ARIA labels where needed
- Keyboard navigation support
- Screen reader friendly
- Color contrast compliance (WCAG AA)

## Contributing

See [CONTRIBUTING.md](../CONTRIBUTING.md) for development guidelines.

## Troubleshooting

### Port Already in Use

```bash
# Kill process on port 3000
lsof -i :3000
kill -9 <PID>

# Or use a different port
PORT=3001 npm run dev
```

### Build Errors

```bash
# Clear Next.js cache
rm -rf .next

# Reinstall dependencies
rm -rf node_modules package-lock.json
npm install

# Rebuild
npm run build
```

### TypeScript Errors

```bash
# Check TypeScript
npx tsc --noEmit

# Update types
npm install --save-dev @types/react @types/node
```

## Resources

- [Next.js Documentation](https://nextjs.org/docs)
- [React Documentation](https://react.dev/)
- [Tailwind CSS Documentation](https://tailwindcss.com/docs)
- [TypeScript Documentation](https://www.typescriptlang.org/docs/)
- [Recharts Documentation](https://recharts.org/)

## License

See [LICENSE](../LICENSE) in the root directory.

---

**Part of Tax Buddy** - AI-Powered Tax Filing Assistant
