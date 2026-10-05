import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Sora Analytics Dashboard",
  description: "Dynamic dashboards powered by Sora Semantic Layer.",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="en"><body>{children}</body></html>;
}
