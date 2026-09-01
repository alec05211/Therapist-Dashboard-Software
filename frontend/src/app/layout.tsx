import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Therapist Sidekick",
  description: "A trusted workspace for therapy session review and practice operations.",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="en" className="h-full antialiased">
      <body className="min-h-full flex flex-col">{children}</body>
    </html>
  );
}
