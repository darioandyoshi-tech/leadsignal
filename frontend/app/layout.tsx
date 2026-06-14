
export const metadata = {
  title: 'LeadSignal — Local Market Opportunity Scanner',
  description: 'Hiring spikes, negative review clusters, and permit filings for Omaha and beyond.',
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="min-h-screen bg-slate-50">{children}</body>
    </html>
  );
}
