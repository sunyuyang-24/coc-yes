import type { Metadata } from "next";
import type { ReactNode } from "react";
import "./globals.css";
import "./room-layout.css";

export const metadata: Metadata = {
  title: "CoC Yes",
  description: "在线克苏鲁的呼唤跑团助手",
  manifest: "/manifest.json",
  appleWebApp: { capable: true, title: "CoC Yes", statusBarStyle: "black-translucent" },
  other: { "mobile-web-app-capable": "yes" },
};

export default function RootLayout({ children }: Readonly<{ children: ReactNode }>) {
  return (
    <html lang="zh-CN" data-background="black">
      <body>{children}</body>
    </html>
  );
}
