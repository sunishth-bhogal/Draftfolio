import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import Link from "next/link";
import "./globals.css";
import { Providers } from "./providers";

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
          <header className="border-b border-line bg-cream/80 backdrop-blur sticky top-0 z-10">
            <div className="mx-auto max-w-6xl px-6 h-16 flex items-center justify-between">
              <Link href="/" className="flex items-center gap-2">
                <span className="inline-block h-3 w-3 rounded-full bg-accent" />
                <span className="font-semibold tracking-tight text-lg">Draftfolio</span>
              </Link>
              <nav className="flex items-center gap-6 text-sm text-ink-soft">
                <Link href="/" className="hover:text-ink transition-colors">
                  Portfolio
                </Link>
                <Link href="/markets" className="hover:text-ink transition-colors">
                  Markets
                </Link>
                <Link href="/leaderboard" className="hover:text-ink transition-colors">
                  Leaderboard
                </Link>
                <Link href="/methodology" className="hover:text-ink transition-colors">
                  Methodology
                </Link>
              </nav>
            </div>
          </header>
          <main className="mx-auto max-w-6xl px-6 py-10">{children}</main>
          <footer className="mx-auto max-w-6xl px-6 py-10 text-xs text-ink-faint border-t border-line mt-10">
            Signals are correlation, not causation. Prices are delayed / point-in-time.
          </footer>
        </Providers>
      </body>
    </html>
  );
}
