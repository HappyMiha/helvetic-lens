import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Helvetic Lens",
  description:
    "See what changed. Understand what matters. Monitor regulatory sources and compare saved evidence.",
};
export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
