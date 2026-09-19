const fs = require('fs');
let page = fs.readFileSync('app/page.tsx', 'utf8');

const imports = 'import { CloudUpload, AlertCircle, MessageSquare, Sparkles, Plus, FileArchive, Lock, ArrowRight, ShieldCheck, Zap, Headphones, Bug, Mail } from "lucide-react";\n';
if (!page.includes('lucide-react')) {
  page = page.replace('import Link from "next/link";\n', 'import Link from "next/link";\n' + imports);
}

const mapPage = [
  ['<span className="material-symbols-outlined text-[20px]">cloud_upload</span>', '<CloudUpload size={20} />'],
  ['<span className="material-symbols-outlined">error</span>', '<AlertCircle size={24} />'],
  ['<span className="material-symbols-outlined text-[60px] rotate-[-15deg]">forum</span>', '<MessageSquare size={60} className="rotate-[-15deg]" />'],
  ['<span className="material-symbols-outlined text-[80px] rotate-[10deg]">auto_awesome</span>', '<Sparkles size={80} className="rotate-[10deg]" />'],
  ['<span className="material-symbols-outlined text-[50px] sm:text-[60px]">cloud_upload</span>', '<CloudUpload className="w-[50px] h-[50px] sm:w-[60px] sm:h-[60px]" />'],
  ['<span className="material-symbols-outlined text-[24px]">add</span>', '<Plus size={24} />'],
  ['<span className="material-symbols-outlined text-[16px] text-primary">folder_zip</span>', '<FileArchive size={16} className="text-primary" />'],
  ['<span className="material-symbols-outlined text-[16px]">lock</span>', '<Lock size={16} />'],
  ['<span className="material-symbols-outlined text-[16px]">arrow_forward</span>', '<ArrowRight size={16} />'],
  ['<span className="material-symbols-outlined text-[16px] text-teal-400">verified_user</span>', '<ShieldCheck size={16} className="text-teal-400" />'],
  ['<span className="material-symbols-outlined text-[16px] text-primary">bolt</span>', '<Zap size={16} className="text-primary" />'],
  ['<span className="material-symbols-outlined text-[18px]">support_agent</span>', '<Headphones size={18} />'],
  ['<span className="material-symbols-outlined text-[18px]">bug_report</span>', '<Bug size={18} />'],
  ['<span className="material-symbols-outlined text-[18px]">mail</span>', '<Mail size={18} />']
];

for (const [s, r] of mapPage) {
  page = page.replace(s, r);
}
fs.writeFileSync('app/page.tsx', page);

let hero = fs.readFileSync('components/PhysicsHero.tsx', 'utf8');
if (!hero.includes('lucide-react')) {
  hero = hero.replace('"use client";\n', '"use client";\nimport { ArrowRight } from "lucide-react";\n');
}
hero = hero.replace('<span className="material-symbols-outlined text-[20px]">arrow_forward</span>', '<ArrowRight size={20} />');
fs.writeFileSync('components/PhysicsHero.tsx', hero);
console.log('done');
