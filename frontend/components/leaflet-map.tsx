'use client';
import 'leaflet/dist/leaflet.css';
import { MapContainer,TileLayer,Polygon,Tooltip,useMap } from 'react-leaflet';
import { useEffect,useState } from 'react';
import type { Neighborhood } from '@/lib/types';
function Focus({selected,neighborhoods}:{selected:string;neighborhoods:Neighborhood[]}){const map=useMap();const center=neighborhoods.find(n=>n.id===selected)?.center;useEffect(()=>{const n=neighborhoods.find(n=>n.id===selected);if(n)map.setView(n.center,map.getZoom(),{animate:map.distance(map.getCenter(),n.center)<20000&&!window.matchMedia('(prefers-reduced-motion: reduce)').matches});},[selected,map,center?.[0],center?.[1]]);return null;}
export default function LeafletMap({selected,onSelect,neighborhoods}:{neighborhoods:Neighborhood[];selected:string;onSelect:(n:Neighborhood)=>void}){
 const [tileError,setTileError]=useState(false);
 return <><MapContainer center={[52.485,13.414]} zoom={13} scrollWheelZoom={false} className="leaflet-map" zoomControl={true}><TileLayer url={process.env.NEXT_PUBLIC_TILE_URL||'https://tile.openstreetmap.org/{z}/{x}/{y}.png'} attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors' eventHandlers={{tileerror:()=>setTileError(true)}}/>{neighborhoods.map(n=><Polygon key={n.id} positions={n.geometry.coordinates[0].map(([lng,lat])=>[lat,lng])} pathOptions={{color:n.color,fillColor:n.color,fillOpacity:selected === n.id ? .38 : .14,weight:selected===n.id?2.5:1.5}} eventHandlers={{click:()=>onSelect(n)}}><Tooltip permanent direction="center" className={`kiez-map-label ${selected===n.id?'selected':''}`}>{n.name}</Tooltip></Polygon>)}<Focus selected={selected} neighborhoods={neighborhoods}/></MapContainer>{tileError&&<div className="tile-error" role="status">Base map unavailable. Choose a neighborhood below.</div>}</>;
}
