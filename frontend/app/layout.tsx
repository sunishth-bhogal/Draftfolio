import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";
import { Providers } from "./providers";
import { Nav } from "@/components/Nav";

const geistSans = Geist({ variable: "--font-geist-sans", subsets: ["latin"] });
const geistMono = Geist_Mono({ variable: "--font-geist-mono", subsets: ["latin"] });

export const metadata: Metadata = {
  title: "Draftfolio",
  description: "Risk-aware fantasy investing — draft, compete, understand.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className={`${geistSans.variable} ${geistMono.variable} antialiased`}>
        <Providers>
          <Nav />
          <div className="pl-[74px]">
            <main className="mx-auto max-w-6xl px-6 py-8 sm:px-10">{children}</main>
            <footer className="mx-auto max-w-6xl px-6 py-10 sm:px-10 text-xs text-ink-faint border-t border-line mt-10">
              Signals are correlation, not causation. Prices are delayed / point-in-time.
            </footer>
          </div>
        </Providers>
      </body>
    </html>
  );
}
