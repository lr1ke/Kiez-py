import * as React from 'react';
import { cn } from '@/lib/utils';
export function Input({className,...props}:React.ComponentProps<'input'>){return <input className={cn('input',className)} {...props}/>;}
export function Textarea({className,...props}:React.ComponentProps<'textarea'>){return <textarea className={cn('input textarea',className)} {...props}/>;}
