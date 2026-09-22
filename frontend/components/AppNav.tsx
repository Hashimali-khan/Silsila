"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { UserButton, SignInButton, useAuth } from "@clerk/nextjs";

const NAV_LINKS = [
  { href: "/", label: "Dashboard" },
  { href: "/upload", label: "Upload" },
];

export function AppNav() {
  const pathname = usePathname();
  const { isLoaded, userId } = useAuth();

  return (
    <header className="fixed top-0 left-0 right-0 z-50 bg-white/90 backdrop-blur-xl border-b border-surface-border">
      <div className="max-w-7xl mx-auto h-16 px-4 sm:px-6 lg:px-8 flex items-center justify-between">
        {/* Brand Logo */}
        <Link href="/" className="flex items-center gap-3 group">
          <img 
            src="/logo.jpg" 
            alt="Silsila AI Logo" 
            className="w-10 h-10 rounded-[12px] object-cover shadow-warm-md group-hover:shadow-warm-lg transition-all duration-300 transform group-hover:-rotate-3 group-hover:scale-105" 
          />
          <div className="flex items-center gap-3">
            <span className="font-display font-black text-2xl tracking-tighter text-on-surface">
              Silsila <span className="text-primary opacity-80 font-extrabold">AI</span>
            </span>
          </div>
        </Link>

        {/* Navigation & Auth Actions */}
        <div className="flex items-center gap-4">
          {isLoaded && userId ? (
            <>
              <nav className="hidden md:flex items-center gap-1.5 p-1 rounded-full bg-surface-muted border border-surface-border mr-2">
                {NAV_LINKS.map((link) => (
                  <Link
                    key={link.href}
                    href={link.href}
                    className={`px-4 py-1.5 rounded-full text-xs font-semibold transition-all ${
                      pathname === link.href
                        ? "bg-primary text-white shadow-warm-sm"
                        : "text-on-surface hover:text-primary"
                    }`}
                  >
                    {link.label}
                  </Link>
                ))}
              </nav>
              <UserButton
                appearance={{
                  elements: {
                    avatarBox: { width: "36px", height: "36px" },
                  },
                }}
              />
            </>
          ) : isLoaded && !userId ? (
            <>
              <SignInButton mode="modal">
                <button className="text-sm font-bold text-on-surface hover:text-primary transition-colors px-4 py-2">
                  Log In
                </button>
              </SignInButton>
              <SignInButton mode="modal">
                <button className="hidden sm:inline-flex bg-primary hover:bg-primary-hover text-white text-sm font-bold px-5 py-2 rounded-full shadow-btn-primary transition-all">
                  Get Started
                </button>
              </SignInButton>
            </>
          ) : (
            <div className="w-8 h-8 rounded-full bg-surface-muted animate-pulse"></div>
          )}
        </div>
      </div>
    </header>
  );
}
