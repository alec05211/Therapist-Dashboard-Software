import type { Metadata } from "next";
import { AppHeader } from "@/components/app-header";
import { ThemeInitializer } from "@/components/theme-initializer";
import "./globals.css";

export const metadata: Metadata = {
  title: "Therapist Sidekick | See the full story of care",
  description: "Longitudinal mental health insights, session review, scheduling, billing, and insurance in one clinician-guided workspace.",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="en" className="h-full antialiased">
      <body className="min-h-full flex flex-col">
        <ThemeInitializer />
        <AppHeader />
        {children}
      </body>
    </html>
  );
}
