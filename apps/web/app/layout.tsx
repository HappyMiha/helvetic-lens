import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Apertus RegWatch",
  description:
    "Know what changed. Know what it means. Know what to do. Monitor regulatory sources and compare saved evidence.",
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
