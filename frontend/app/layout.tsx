import type { Metadata } from 'next';
import './globals.css';
export const metadata: Metadata = { title: 'SkillForge — Show it once. Learn it anywhere.', description: 'Physical skills, made transferable.' };
export default function Layout({ children }: { children: React.ReactNode }) { return <html lang="en"><body>{children}</body></html>; }
