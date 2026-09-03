import type { Metadata } from "next";
import "./globals.css";
import { AuthGate } from "@/components/auth-gate";
import { I18nProvider } from "@/lib/i18n";

export const metadata: Metadata = {
  title: "Helvetic Lens",
  description:
    "See what changed. Understand what matters. Monitor regulatory sources and compare saved evidence.",
};
export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en-CH" suppressHydrationWarning>
      <body>
        <I18nProvider>
          <AuthGate>{children}</AuthGate>
        </I18nProvider>
      </body>
    </html>
  );
}
