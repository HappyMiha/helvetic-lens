import type { Metadata } from "next";
import "./globals.css";
import "./native-brand.css";
import "./reading-themes.css";
import { ThemeProvider } from "@/components/theme-provider";
import { THEME_BOOTSTRAP } from "@/lib/theme-preference";
import { AuthGate } from "@/components/auth-gate";
import { NativeAskSearchProvider } from "@/components/native-ask-search";
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
    <html
      lang="en-CH"
      className="dark"
      data-theme="dark"
      suppressHydrationWarning
    >
      <head>
        <script
          id="helvetic-theme"
          dangerouslySetInnerHTML={{ __html: THEME_BOOTSTRAP }}
        />
      </head>
      <body>
        <I18nProvider>
          <ThemeProvider>
            <AuthGate>
              <NativeAskSearchProvider>{children}</NativeAskSearchProvider>
            </AuthGate>
          </ThemeProvider>
        </I18nProvider>
      </body>
    </html>
  );
}
