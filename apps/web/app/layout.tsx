import type { ReactNode } from "react";
import "./globals.css";

export const metadata = {
  title: "HalfSpace | Match analysis",
  description: "Explore football sequences through a broadcast analyst's lens.",
};

export default function RootLayout({ children }: Readonly<{ children: ReactNode }>) {
  return <html lang="en"><body>{children}</body></html>;
}
