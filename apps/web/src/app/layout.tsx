import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "ScamShield — Always-On Scam Protection",
  description: "Real-time scam detection and investigation for your inbox and beyond.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className="dark">
      <body className="min-h-screen bg-[var(--background)] text-[var(--foreground)] antialiased">
        {children}
      </body>
    </html>
  );
}
