'use client';
export default function ErrorPage({reset}:{reset:()=>void}){return <main id="main" className="archive-page"><h1>A little interruption.</h1><p>The notes couldn’t load. Your saved moments are safe.</p><button className="button button-primary" onClick={reset}>Try again</button></main>;}
