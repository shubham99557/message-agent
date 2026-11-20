import React from 'react';
import { ViewType } from '../types';
import { ShieldCheck, Lock, MapPin, Send, Sparkles } from 'lucide-react';

interface HeaderProps {
  currentView: ViewType;
  title: string;
  subtitle?: string;
}

export const Header: React.FC<HeaderProps> = ({ currentView, title, subtitle }) => {
  return (
    <header className="h-16 border-b border-cobalt-800/80 bg-cobalt-950/95 backdrop-blur-sm px-6 flex items-center justify-between sticky top-0 z-10">
      <div>
        <h1 className="text-base font-semibold text-slate-100 tracking-tight">{title}</h1>
        {subtitle && <p className="text-xs text-slate-400 mt-0.5">{subtitle}</p>}
      </div>

      <div className="flex items-center space-x-3 text-xs">
        {/* Local AI Brain Badge */}
        <div className="hidden sm:flex items-center space-x-1.5 px-2.5 py-1 rounded bg-cobalt-900 border border-cobalt-800 text-slate-300">
          <Sparkles className="w-3.5 h-3.5 text-amber-400" />
          <span className="font-mono text-[11px]">Local AI: llama3.2 (CUDA)</span>
        </div>

        {/* City Filter / Market Badge */}
        <div className="hidden md:flex items-center space-x-1.5 px-2.5 py-1 rounded bg-cobalt-900 border border-cobalt-800 text-slate-300">
          <MapPin className="w-3.5 h-3.5 text-cobalt-400" />
          <span className="font-mono text-[11px]">Siliguri • Gangtok • Patna • Bhagalpur</span>
        </div>

        {/* Safety & Sending Limit Badge */}
        <div className="hidden lg:flex items-center space-x-1.5 px-2.5 py-1 rounded bg-cobalt-900 border border-cobalt-800 text-slate-300">
          <Send className="w-3.5 h-3.5 text-emerald-400" />
          <span className="font-mono text-[11px]">Limit: 50 emails/day</span>
        </div>

        {/* Human In The Loop Enforcement Indicator */}
        <div className="flex items-center space-x-1.5 px-2.5 py-1 rounded bg-amber-500/10 border border-amber-500/30 text-amber-300">
          <Lock className="w-3.5 h-3.5 text-amber-400" />
          <span className="font-mono text-[11px] font-medium uppercase tracking-wider">Approval Required</span>
        </div>
      </div>
    </header>
  );
};
