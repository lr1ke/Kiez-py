import type { Metadata } from 'next';
import './globals.css';
import { Header, Footer } from '@/components/header';
export const metadata:Metadata={title:{default:'Kiez Notes — Every place has a story',template:'%s · Kiez Notes'},description:'The neighborhood, told by its people. Share a moment, discover a Kiez, and listen to its collective memory.'};
export default function RootLayout({children}:{children:React.ReactNode}){return <html lang="en" data-scroll-behavior="smooth"><body><a href="#main" className="skip-link">Skip to content</a><Header/>{children}<Footer/></body></html>;}
