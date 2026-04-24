import type { Metadata } from 'next';
import { Inter } from 'next/font/google';
import './globals.css';
import { Toaster } from 'sonner';

const inter = Inter({ subsets: ['latin'], variable: '--font-inter' });

export const metadata: Metadata = {
  title: 'Tax Buddy — AI Tax Filing Assistant',
  description: 'OCR + NLP powered Indian income tax analysis. Upload Form 16 and get instant tax computation.',
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className="dark" suppressHydrationWarning>
      <body className={`${inter.variable} font-sans antialiased bg-[#0a0b0f] text-slate-100 min-h-screen`}>
        {children}
        <Toaster
          position="top-right"
          toastOptions={{
            style: {
              background: '#1a1d27',
              border: '1px solid #2a2d3a',
              color: '#e2e8f0',
            },
          }}
        />
      </body>
    </html>
  );
}
