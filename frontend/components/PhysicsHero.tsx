"use client";
import { ArrowRight } from "lucide-react";

import { useEffect, useRef } from "react";
import { SignUpButton } from "@clerk/nextjs";

export function PhysicsHero() {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    const container = containerRef.current;
    if (!canvas || !container) return;

    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const dpr = window.devicePixelRatio || 1;

    let width = container.clientWidth;
    let height = container.clientHeight;

    canvas.width = width * dpr;
    canvas.height = height * dpr;
    canvas.style.width = `${width}px`;
    canvas.style.height = `${height}px`;
    ctx.scale(dpr, dpr);

    const handleResize = () => {
      width = container.clientWidth;
      height = container.clientHeight;
      canvas.width = width * dpr;
      canvas.height = height * dpr;
      canvas.style.width = `${width}px`;
      canvas.style.height = `${height}px`;
      ctx.setTransform(1, 0, 0, 1, 0, 0); // Reset transform
      ctx.scale(dpr, dpr);
    };
    window.addEventListener("resize", handleResize);

    // Clean warm color tags (Glassmorphism RGBA values)
    const pillTags = [
      { text: "inside jokes ✨", bg: "rgba(255, 247, 237, 0.7)", textCol: "#C2410C", borderCol: "rgba(255, 255, 255, 0.8)" },
      { text: "late night talks 🌙", bg: "rgba(248, 250, 252, 0.7)", textCol: "#334155", borderCol: "rgba(255, 255, 255, 0.8)" },
      { text: "vacation planning ✈️", bg: "rgba(236, 253, 245, 0.7)", textCol: "#047857", borderCol: "rgba(255, 255, 255, 0.8)" },
      { text: "coffee runs ☕", bg: "rgba(254, 243, 199, 0.7)", textCol: "#B45309", borderCol: "rgba(255, 255, 255, 0.8)" },
      { text: "shared playlists 🎵", bg: "rgba(241, 245, 249, 0.7)", textCol: "#1E293B", borderCol: "rgba(255, 255, 255, 0.8)" },
      { text: "unfiltered rants 💬", bg: "rgba(255, 241, 242, 0.7)", textCol: "#BE123C", borderCol: "rgba(255, 255, 255, 0.8)" },
      { text: "3 AM memes 😂", bg: "rgba(254, 249, 195, 0.7)", textCol: "#A16207", borderCol: "rgba(255, 255, 255, 0.8)" },
      { text: "road trips 🚗", bg: "rgba(240, 253, 244, 0.7)", textCol: "#15803D", borderCol: "rgba(255, 255, 255, 0.8)" }
    ];

    // Read the computed Next.js font variable so it matches exactly
    const displayFont = window.getComputedStyle(document.documentElement).getPropertyValue('--font-display').trim() || "'Outfit', sans-serif";
    
    ctx.font = `800 14px ${displayFont}`;
    const pills = pillTags.map((tag, i) => {
      const metrics = ctx.measureText(tag.text);
      const w = metrics.width + 42; // slightly wider for glass padding
      const h = 42; // slightly taller
      const col = i % 4;
      const row = Math.floor(i / 4);
      return {
        x: 60 + col * (width / 4.2) + Math.random() * 20,
        y: (row === 0 ? height * 0.18 : height * 0.72) + Math.random() * 30,
        vx: (Math.random() - 0.5) * 1.5,
        vy: (Math.random() - 0.5) * 1.3,
        w: w,
        h: h,
        radius: 19,
        tag: tag,
        isDragging: false
      };
    });

    let draggedPill: any = null;
    let mouseX = 0;
    let mouseY = 0;
    let lastMouseX = 0;
    let lastMouseY = 0;

    function getPointerPos(e: any) {
      const rect = canvas!.getBoundingClientRect();
      const clientX = e.touches ? e.touches[0].clientX : e.clientX;
      const clientY = e.touches ? e.touches[0].clientY : e.clientY;
      return {
        x: clientX - rect.left,
        y: clientY - rect.top
      };
    }

    function onPointerDown(e: any) {
      const pos = getPointerPos(e);
      mouseX = pos.x;
      mouseY = pos.y;
      lastMouseX = mouseX;
      lastMouseY = mouseY;

      for (let i = pills.length - 1; i >= 0; i--) {
        const p = pills[i];
        if (
          mouseX >= p.x - p.w / 2 &&
          mouseX <= p.x + p.w / 2 &&
          mouseY >= p.y - p.h / 2 &&
          mouseY <= p.y + p.h / 2
        ) {
          draggedPill = p;
          p.isDragging = true;
          p.vx = 0;
          p.vy = 0;
          break;
        }
      }
    }

    function onPointerMove(e: any) {
      const pos = getPointerPos(e);
      mouseX = pos.x;
      mouseY = pos.y;
      if (draggedPill) {
        draggedPill.vx = (mouseX - lastMouseX) * 0.8;
        draggedPill.vy = (mouseY - lastMouseY) * 0.8;
        draggedPill.x = mouseX;
        draggedPill.y = mouseY;
      }
      lastMouseX = mouseX;
      lastMouseY = mouseY;
    }

    function onPointerUp() {
      if (draggedPill) {
        draggedPill.isDragging = false;
        draggedPill = null;
      }
    }

    canvas.addEventListener('mousedown', onPointerDown);
    window.addEventListener('mousemove', onPointerMove);
    window.addEventListener('mouseup', onPointerUp);
    canvas.addEventListener('touchstart', onPointerDown, { passive: true });
    window.addEventListener('touchmove', onPointerMove, { passive: true });
    window.addEventListener('touchend', onPointerUp);

    function drawRoundedRect(ctx: CanvasRenderingContext2D, x: number, y: number, width: number, height: number, radius: number) {
      ctx.beginPath();
      ctx.moveTo(x + radius, y);
      ctx.lineTo(x + width - radius, y);
      ctx.quadraticCurveTo(x + width, y, x + width, y + radius);
      ctx.lineTo(x + width, y + height - radius);
      ctx.quadraticCurveTo(x + width, y + height, x + width - radius, y + height);
      ctx.lineTo(x + radius, y + height);
      ctx.quadraticCurveTo(x, y + height, x, y + height - radius);
      ctx.lineTo(x, y + radius);
      ctx.quadraticCurveTo(x, y, x + radius, y);
      ctx.closePath();
    }

    let animationFrameId: number;

    function animate() {
      if (!ctx || !canvas) return;
      ctx.clearRect(0, 0, width, height);

      for (let i = 0; i < pills.length; i++) {
        const p = pills[i];

        if (!p.isDragging) {
          p.vx *= 0.99;
          p.vy *= 0.99;
          p.x += p.vx;
          p.y += p.vy;

          const halfW = p.w / 2;
          const halfH = p.h / 2;

          if (p.x - halfW < 12) {
            p.x = 12 + halfW;
            p.vx = -p.vx * 0.85;
          } else if (p.x + halfW > width - 12) {
            p.x = width - 12 - halfW;
            p.vx = -p.vx * 0.85;
          }

          if (p.y - halfH < 12) {
            p.y = 12 + halfH;
            p.vy = -p.vy * 0.85;
          } else if (p.y + halfH > height - 12) {
            p.y = height - 12 - halfH;
            p.vy = -p.vy * 0.85;
          }

          for (let j = i + 1; j < pills.length; j++) {
            const p2 = pills[j];
            const dx = p2.x - p.x;
            const dy = p2.y - p.y;
            const dist = Math.sqrt(dx * dx + dy * dy);
            const minDist = (p.w + p2.w) / 4 + 20;

            if (dist < minDist && dist > 0) {
              const angle = Math.atan2(dy, dx);
              const overlap = (minDist - dist) * 0.5;
              const pushX = Math.cos(angle) * overlap;
              const pushY = Math.sin(angle) * overlap;

              if (!p.isDragging) {
                p.x -= pushX * 0.5;
                p.y -= pushY * 0.5;
                p.vx -= pushX * 0.1;
                p.vy -= pushY * 0.1;
              }
              if (!p2.isDragging) {
                p2.x += pushX * 0.5;
                p2.y += pushY * 0.5;
                p2.vx += pushX * 0.1;
                p2.vy += pushY * 0.1;
              }
            }
          }
        }

        // Draw Glassmorphic Pill Base
        ctx.save();
        ctx.shadowColor = 'rgba(0, 0, 0, 0.08)';
        ctx.shadowBlur = 12;
        ctx.shadowOffsetY = 6;

        ctx.fillStyle = p.tag.bg;
        drawRoundedRect(ctx, p.x - p.w / 2, p.y - p.h / 2, p.w, p.h, p.radius);
        ctx.fill();
        ctx.restore();

        // Draw Glassy Highlight Border
        ctx.save();
        ctx.strokeStyle = p.tag.borderCol;
        ctx.lineWidth = 1.5;
        drawRoundedRect(ctx, p.x - p.w / 2, p.y - p.h / 2, p.w, p.h, p.radius);
        ctx.stroke();
        ctx.restore();

        // Draw Premium Typography
        ctx.fillStyle = p.tag.textCol;
        ctx.font = `800 14px ${displayFont}`;
        ctx.textAlign = "center";
        ctx.textBaseline = "middle";
        ctx.fillText(p.tag.text, p.x, p.y);
      }

      animationFrameId = requestAnimationFrame(animate);
    }

    animate();

    return () => {
      window.removeEventListener("resize", handleResize);
      if (canvas) {
        canvas.removeEventListener('mousedown', onPointerDown);
        window.removeEventListener('mousemove', onPointerMove);
        window.removeEventListener('mouseup', onPointerUp);
        canvas.removeEventListener('touchstart', onPointerDown);
        window.removeEventListener('touchmove', onPointerMove);
        window.removeEventListener('touchend', onPointerUp);
      }
      cancelAnimationFrame(animationFrameId);
    };
  }, []);

  return (
    <section className="relative min-h-[640px] lg:min-h-[720px] w-full flex flex-col items-center justify-center px-4 sm:px-6 lg:px-8 pt-10 pb-16 overflow-hidden">
      {/* Atmospheric Warm Neutral Glow */}
      <div className="absolute -top-20 left-1/2 -translate-x-1/2 w-[720px] h-[480px] bg-gradient-to-b from-orange-100/60 via-amber-50/40 to-transparent blur-3xl rounded-full pointer-events-none -z-10"></div>
      <div className="absolute top-1/3 -left-20 w-80 h-80 bg-orange-100/30 blur-3xl rounded-full pointer-events-none -z-10"></div>
      <div className="absolute bottom-10 -right-20 w-80 h-80 bg-amber-100/40 blur-3xl rounded-full pointer-events-none -z-10"></div>
      
      {/* Physics Pills Canvas Container */}
      <div 
        ref={containerRef}
        className="absolute inset-0 w-full h-full pointer-events-auto overflow-hidden -z-0"
      >
        <canvas ref={canvasRef} className="w-full h-full block" />
      </div>
      
      {/* Hero Central Typography & Call To Action */}
      <div className="relative z-10 max-w-4xl mx-auto text-center flex flex-col items-center pointer-events-none">
        <div className="pointer-events-auto inline-flex items-center gap-2 px-4 py-1.5 rounded-full bg-white/95 backdrop-blur-md border border-surface-border shadow-warm-sm mb-6 hover:scale-105 transition-transform">
          <span className="flex h-2 w-2 rounded-full bg-primary animate-pulse"></span>
          <span className="text-xs font-bold tracking-wide text-on-surface">Every Chat is a Living Story</span>
        </div>
        <h1 className="font-display font-extrabold text-4xl sm:text-6xl lg:text-7xl tracking-tight text-on-surface leading-[1.1] max-w-3xl">
          Understand your relationships,
          <span className="gradient-text-warm block mt-1 sm:mt-2">not just your texts.</span>
        </h1>
        <p className="font-body text-base sm:text-xl text-on-surface-variant max-w-2xl mt-6 leading-relaxed">
          Turn endless WhatsApp group banter, family voice notes, late-night chai debates, road trips to the North, and heart-to-heart moments into living, searchable memories.
        </p>
        
        {/* CTAs */}
        <div className="pointer-events-auto flex flex-wrap items-center justify-center gap-3.5 mt-8">
          <SignUpButton mode="modal">
            <button className="bg-primary hover:bg-primary-hover text-white font-display font-bold px-8 py-4 rounded-full shadow-btn-primary hover:scale-105 active:scale-95 transition-all flex items-center gap-2 text-base sm:text-lg">
              <span>Get Started</span>
              <ArrowRight size={20} />
            </button>
          </SignUpButton>
        </div>
      </div>
    </section>
  );
}
