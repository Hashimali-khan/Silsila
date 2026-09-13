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

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <ClerkProvider>
      <html lang="en" className="h-full">
        <body className="h-full antialiased">
          {children}
        </body>
      </html>
    </ClerkProvider>
  );
}