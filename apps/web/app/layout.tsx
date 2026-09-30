import type { ReactNode } from "react";

export const metadata = { title: "HalfSpace", description: "Football sequence analysis" };

export default function RootLayout({ children }: Readonly<{ children: ReactNode }>) {
  return <html lang="en"><body>{children}</body></html>;
}
