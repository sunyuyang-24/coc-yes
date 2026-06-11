import type { Metadata } from "next";
import type { ReactNode } from "react";
import "./globals.css";

export const metadata: Metadata = {
  title: "CoC Yes",
  description: "在线克苏鲁的呼唤跑团助手 — 房间、语音、骰子、角色卡、规则书，即开即用",
  manifest: "/manifest.json",
  appleWebApp: {
    capable: true,
    title: "CoC Yes",
    statusBarStyle: "black-translucent",
  },
  other: {
    "mobile-web-app-capable": "yes",
  },
};

export default function RootLayout({
  children
}: Readonly<{
  children: ReactNode;
}>) {
  return (
    <html lang="zh-CN" data-background="black">
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="anonymous" />
        <link href="https://fonts.googleapis.com/css2?family=Cinzel:wght@500;700;900&family=Noto+Sans+SC:wght@400;600;700&family=Noto+Serif+SC:wght@400;600;700&display=swap" rel="stylesheet" />
      </head>
      <body>{children}</body>
    </html>
  );
}
