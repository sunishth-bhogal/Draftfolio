import Link from "next/link";

export function Card({ children, className = "" }: { children: React.ReactNode; className?: string }) {
  return (
    <div className={`rounded-2xl bg-card border border-line p-6 ${className}`}>{children}</div>
  );
}

export function StatTile({
  label,
  value,
  tone = "",
  hint,
}: {
  label: string;
  value: string;
  tone?: string;
  hint?: string;
}) {
  return (
    <div className="rounded-xl border border-line bg-card px-4 py-3">
      <div className="text-xs uppercase tracking-wide text-ink-faint">{label}</div>
      <div className={`num text-2xl font-semibold mt-1 ${tone}`}>{value}</div>
      {hint && <div className="text-xs text-ink-faint mt-0.5">{hint}</div>}
    </div>
  );
}

/** Horizontal weight/percentile bar. */
export function Bar({ value, tone = "bg-accent" }: { value: number; tone?: string }) {
  return (
    <div className="h-2 w-full rounded-full bg-line overflow-hidden">
      <div className={`h-full rounded-full ${tone}`} style={{ width: `${Math.max(0, Math.min(1, value)) * 100}%` }} />
    </div>
  );
}

export function LinkButton({ href, children }: { href: string; children: React.ReactNode }) {
  return (
    <Link
      href={href}
      className="text-sm text-accent-deep underline underline-offset-4 decoration-line hover:decoration-accent-deep transition"
    >
      {children}
    </Link>
  );
}
