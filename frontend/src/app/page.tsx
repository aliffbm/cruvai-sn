import Link from "next/link";

export default function Home() {
  return (
    <div className="flex min-h-screen flex-col items-center justify-center gap-8 p-8">
      <div className="text-center">
        <h1 className="text-5xl font-bold tracking-tight">
          Cruvai <span className="text-[var(--primary)]">ServiceNow</span> Developer
        </h1>
        <p className="mt-4 text-lg text-[var(--muted-foreground)] max-w-xl mx-auto">
          AI agents that build ServiceNow solutions from user stories.
          Catalog items, flows, business rules, ATF tests — all deployed automatically.
        </p>
      </div>
      <div className="flex gap-4">
        <Link
          href="/login"
          className="rounded-lg border border-[var(--border)] px-6 py-3 text-sm font-medium hover:bg-[var(--secondary)] transition-colors"
        >
          Sign In
        </Link>
        <Link
          href="/register"
          className="rounded-lg bg-[var(--primary)] px-6 py-3 text-sm font-medium text-[var(--primary-foreground)] hover:opacity-90 transition-opacity"
        >
          Get Started
        </Link>
      </div>
    </div>
  );
}
