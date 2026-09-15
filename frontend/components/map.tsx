'use client';
import dynamic from 'next/dynamic';
import { Skeleton } from './ui/skeleton';
import type { Neighborhood } from '@/lib/types';
const LeafletMap=dynamic(()=>import('./leaflet-map'),{ssr:false,loading:()=> <Skeleton className="map-loading"/>});
export function Map({selected,onSelect,neighborhoods}:{neighborhoods:Neighborhood[];selected:string;onSelect:(n:Neighborhood)=>void}){return <LeafletMap neighborhoods={neighborhoods} selected={selected} onSelect={onSelect}/>;}
