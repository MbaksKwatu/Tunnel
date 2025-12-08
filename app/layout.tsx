import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";

const inter = Inter({ subsets: ["latin"] });

export const metadata: Metadata = {
  title: "Parity - AI Investment Intelligence",
  description: "AI-native financial analysis and due diligence platform",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className="dark">
      <body className={`${inter.className} bg-base-950 text-gray-200 antialiased`}>
        {children}
      </body>
    </html>
  );
}


