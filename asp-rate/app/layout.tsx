import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "asp-rate: ocijeni težinu zadatka",
  description: "Pomoć pri istraživanju težine ASP ispitnih zadataka.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="hr">
      <body>{children}</body>
    </html>
  );
}
