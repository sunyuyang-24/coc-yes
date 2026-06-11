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
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="anonymous" />
        <link href="https://fonts.googleapis.com/css2?family=Cormorant+Garamond:ital,wght@0,400;0,600;0,700;1,400;1,600&family=JetBrains+Mono:wght@400;600;700&display=swap" rel="stylesheet" />
      </head>
      <body>
        <div className="noise-overlay" aria-hidden="true" />
        {children}
      </body>
    </html>
  );
}
