import type { Metadata } from "next";
import { ClerkProvider } from "@clerk/nextjs";
import "./globals.css";

export const metadata: Metadata = {
  title: "Silsila — AI Memory Engine",
  description:
    "Rediscover your conversations. Ask questions, trace relationships, and uncover the story of your connections through AI-powered chat analysis.",
  keywords: ["WhatsApp analysis", "chat history", "AI memory", "relationship intelligence"],
  openGraph: {
    title: "Silsila — AI Memory Engine",
    description: "Your conversations, remembered and understood.",
    type: "website",
  },
};

import { Outfit, Manrope } from "next/font/google";

const fontOutfit = Outfit({
  subsets: ["latin"],
  variable: "--font-outfit",
});

const fontManrope = Manrope({
  subsets: ["latin"],
  variable: "--font-manrope",
});

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <ClerkProvider
      appearance={{
        variables: {
          colorPrimary: '#EA580C',
          colorBackground: '#ffffff',
          colorText: '#0F172A',
          colorTextSecondary: '#475569',
          fontFamily: 'var(--font-manrope)',
          borderRadius: '1rem',
        },
        elements: {
          card: "rounded-[1.35rem] shadow-warm-xl border border-surface-border bg-white backdrop-blur-xl",
          headerTitle: "font-display font-extrabold text-2xl tracking-tight text-on-surface",
          headerSubtitle: "text-on-surface-subtle",
          formButtonPrimary: "bg-primary hover:bg-primary-hover shadow-btn-primary transition-all font-bold",
          socialButtonsBlockButton: "border-surface-border hover:bg-surface-muted transition-colors text-on-surface font-semibold rounded-xl",
          socialButtonsBlockButtonText: "font-semibold",
          dividerText: "text-on-surface-subtle",
          formFieldLabel: "text-on-surface-variant font-semibold",
          formFieldInput: "rounded-xl border-surface-border focus:border-primary focus:ring-primary/20",
          footerActionLink: "text-primary hover:text-primary-hover font-bold",
        }
      }}
    >
      <html lang="en" className={`h-full ${fontOutfit.variable} ${fontManrope.variable}`} data-scroll-behavior="smooth">
        <head>
          <link href="https://fonts.googleapis.com/css2?family=Material+Symbols+Outlined:opsz,wght,FILL,GRAD@20..48,100..700,0..1,-50..200" rel="stylesheet" />
        </head>
        <body className="h-full antialiased font-body text-on-surface bg-background min-h-screen selection:bg-primary/15 selection:text-primary">
          {children}
        </body>
      </html>
    </ClerkProvider>
  );
}