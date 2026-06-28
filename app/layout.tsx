import type { Metadata } from "next";
import "./globals.css";
import { plexSans, plexMono } from "./fonts";
import { AuthProvider } from "@/components/AuthProvider";
import ReactQueryProvider from '@/components/ReactQueryProvider'

export const metadata: Metadata = {
  title: "Parity PDS - Deal Analysis",
  description: "Deterministic v1 deal analysis and snapshot export",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className={`dark ${plexSans.variable} ${plexMono.variable}`}>
      <body className="font-body bg-base-950 text-gray-200 antialiased">
        <ReactQueryProvider>
          <AuthProvider>
            {children}
          </AuthProvider>
        </ReactQueryProvider>
      </body>
    </html>
  );
}


