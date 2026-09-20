import type { Metadata, Viewport } from "next";
import { AppNav } from "@/components/AppNav";
import { SpiderSolitaire } from "@/components/SpiderSolitaire";
import "./globals.css";

export const metadata: Metadata = {
  title: "有谱了",
  description: "校音、节拍、扒谱、移调。",
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  viewportFit: "cover",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="zh-CN">
      <body>
        <SpiderSolitaire />
        {children}
        <AppNav />
      </body>
    </html>
  );
}
