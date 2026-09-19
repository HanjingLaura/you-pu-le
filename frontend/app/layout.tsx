import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "有谱了",
  description: "上传钢琴独奏，扒成大谱表草稿。",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="zh-CN">
      <body>{children}</body>
    </html>
  );
}
