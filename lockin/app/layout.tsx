import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "LockIn — your AI study coach",
  description:
    "Tell LockIn your goal and deadline. It builds you a personal day-by-day study plan in seconds.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
