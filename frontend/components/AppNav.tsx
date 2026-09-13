"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { UserButton } from "@clerk/nextjs";

const NAV_LINKS = [
  { href: "/", label: "Dashboard", icon: "⊞" },
  { href: "/upload", label: "Upload", icon: "↑" },
];

export function AppNav() {
  const pathname = usePathname();

  return (
    <header
      style={{
        background: "var(--surface)",
        borderBottom: "1px solid var(--border)",
        position: "sticky",
        top: 0,
        zIndex: 50,
        height: "60px",
        display: "flex",
        alignItems: "center",
        padding: "0 1.5rem",
        gap: "1rem",
      }}
    >
      {/* Logo */}
      <Link
        href="/"
        style={{
          display: "flex",
          alignItems: "center",
          gap: "0.5rem",
          textDecoration: "none",
          marginRight: "1rem",
        }}
      >
        <span
          style={{
            width: "28px",
            height: "28px",
            background: "var(--orange-600)",
            borderRadius: "8px",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            fontSize: "14px",
          }}
        >
          🔗
        </span>
        <span
          style={{
            fontFamily: "'Plus Jakarta Sans', sans-serif",
            fontWeight: 700,
            fontSize: "1.1rem",
            color: "var(--text-primary)",
            letterSpacing: "-0.02em",
          }}
        >
          Silsila
        </span>
      </Link>

      {/* Nav links */}
      <nav style={{ display: "flex", gap: "0.25rem", flex: 1 }}>
        {NAV_LINKS.map((link) => (
          <Link
            key={link.href}
            href={link.href}
            style={{
              display: "flex",
              alignItems: "center",
              gap: "0.375rem",
              padding: "0.375rem 0.875rem",
              borderRadius: "var(--radius-md)",
              textDecoration: "none",
              fontSize: "0.875rem",
              fontWeight: 500,
              background:
                pathname === link.href
                  ? "var(--orange-50)"
                  : "transparent",
              color:
                pathname === link.href
                  ? "var(--orange-700)"
                  : "var(--text-secondary)",
              transition: "all 0.15s ease",
            }}
          >
            <span style={{ fontSize: "0.9rem" }}>{link.icon}</span>
            {link.label}
          </Link>
        ))}
      </nav>

      {/* User */}
      <UserButton
        appearance={{
          elements: {
            avatarBox: { width: "32px", height: "32px" },
          },
        }}
      />
    </header>
  );
}
