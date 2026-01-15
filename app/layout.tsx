import type { Metadata } from "next";
import { Inter } from "next/font/google";
import { Analytics } from "@vercel/analytics/react";
import "./globals.css";
import Navigation from "@/components/Navigation";
import { AuthProvider } from "@/components/AuthProvider";

// Import Inter font
const inter = Inter({ 
  subsets: ["latin"],
  variable: "--font-inter",
  display: "swap",
});

export const metadata: Metadata = {
  title: "Parity - Investment Judgment Engine",
  description: "AI-powered investment judgment for emerging markets",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className={`dark ${inter.variable}`}>
      <body className="font-body bg-base-950 text-gray-200 antialiased">
        <AuthProvider>
          <Navigation />
          {children}
        </AuthProvider>
        <Analytics />
      </body>
    </html>
  );
}


