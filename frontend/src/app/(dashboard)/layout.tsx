"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const navItems = [
  { href: "/projects", label: "Projects", icon: "folder" },
  { href: "/instances", label: "Instances", icon: "server" },
  { href: "/connectors", label: "Connectors", icon: "plug" },
  { href: "/review", label: "Reviews", icon: "check-circle" },
  { href: "/control-plane", label: "Control Plane", icon: "cpu" },
  { href: "/knowledge-base", label: "Knowledge Base", icon: "book" },
  { href: "/admin/settings", label: "Settings", icon: "settings" },
];

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();

  return (
    <div className="flex min-h-screen">
      {/* Sidebar */}
      <aside className="w-64 border-r border-[var(--border)] bg-[var(--card)] flex flex-col">
        <div className="p-4 border-b border-[var(--border)]">
          <Link href="/projects" className="flex items-center gap-2">
            <span className="text-lg font-bold">
              Cruvai <span className="text-[var(--primary)]">SN</span>
            </span>
          </Link>
        </div>
        <nav className="flex-1 p-3 space-y-1">
          {navItems.map((item) => {
            const isActive = pathname.startsWith(item.href);
            return (
              <Link
                key={item.href}
                href={item.href}
                className={`flex items-center gap-3 rounded-lg px-3 py-2 text-sm transition-colors ${
                  isActive
                    ? "bg-[var(--primary)]/10 text-[var(--primary)]"
                    : "text-[var(--muted-foreground)] hover:text-[var(--foreground)] hover:bg-[var(--secondary)]"
                }`}
              >
                {item.label}
              </Link>
            );
          })}
        </nav>
      </aside>

      {/* Main content */}
      <main className="flex-1 overflow-auto">
        <div className="p-6">{children}</div>
      </main>
    </div>
  );
}
