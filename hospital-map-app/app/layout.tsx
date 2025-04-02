import type { Metadata } from "next";
import { HospitalProvider } from './context/HospitalContext';
import { TransparencyProvider } from './context/TransparencyContext';
import "./globals.css";

export const metadata: Metadata = {
  title: "NeoMed Atlas | US Hospital Interactive Map",
  description: "Interactive cyberpunk-styled US hospital map",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body>
        <HospitalProvider>
          <TransparencyProvider>
            <div className="mx-auto max-w-screen-2xl">
              {children}
            </div>
          </TransparencyProvider>
        </HospitalProvider>
      </body>
    </html>
  );
}
