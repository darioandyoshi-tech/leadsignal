import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";
import "leaflet/dist/leaflet.css";

const inter = Inter({
  subsets: ["latin"],
  variable: "--font-inter",
});

export const metadata: Metadata = {
  title: "LeadSignal — Local Market Intelligence",
  description:
    "Turn local market signals into action: hiring spikes, permits, parcels, tax delinquencies, government contracts, land-bank properties, and more.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className={inter.variable}>
      <body className="font-sans min-h-screen bg-noir-950 text-noir-100">{children}</body>
    </html>
  );
}
