import type { Config } from "tailwindcss";

const config = {
  darkMode: ["class"],
  content: [
    './pages/**/*.{ts,tsx}',
    './components/**/*.{ts,tsx}',
    './app/**/*.{ts,tsx}',
    './src/**/*.{ts,tsx}',
  ],
  prefix: "",
  theme: {
    container: {
      center: true,
      padding: "2rem",
      screens: {
        "2xl": "1440px",
      },
    },
    extend: {
      fontFamily: {
        sans: ["var(--font-inter)", "sans-serif"],
        heading: ["var(--font-space-grotesk)", "var(--font-outfit)", "sans-serif"],
        mono: ["var(--font-jetbrains-mono)", "monospace"],
      },
      colors: {
        border: {
          DEFAULT: "var(--border-subtle)",
          primary: "var(--border-primary)",
          active: "var(--border-active)",
        },
        input: "var(--border-subtle)",
        ring: "var(--accent-primary)",
        background: "var(--bg-primary)",
        foreground: "var(--text-primary)",
        bg: {
          primary: "var(--bg-primary)",
          secondary: "var(--bg-secondary)",
          tertiary: "var(--bg-tertiary)",
          elevated: "var(--bg-elevated)",
          sidebar: "var(--bg-sidebar)",
          glass: "var(--bg-glass)",
        },
        accent: {
          primary: "var(--accent-primary)",
          "primary-hover": "var(--accent-hover)",
          secondary: "var(--accent-secondary)",
          highlight: "var(--accent-highlight)",
        },
        platform: {
          youtube: "var(--platform-youtube)",
          tiktok: "var(--platform-tiktok)",
          instagram: "var(--platform-instagram)",
          facebook: "var(--platform-facebook)",
          twitter: "var(--platform-twitter)",
          whatsapp: "var(--platform-whatsapp)",
        },
        status: {
          success: "var(--status-success)",
          warning: "var(--status-warning)",
          error: "var(--status-error)",
          info: "var(--status-info)",
          downloading: "var(--status-downloading)",
          queued: "var(--status-queued)",
          paused: "var(--status-paused)",
        },
        text: {
          primary: "var(--text-primary)",
          secondary: "var(--text-secondary)",
          muted: "var(--text-muted)",
          disabled: "var(--text-disabled)",
          link: "var(--text-link)",
        },
      },
      borderRadius: {
        lg: "16px",
        md: "12px",
        sm: "8px",
      },
      backgroundImage: {
        'gradient-primary': 'var(--gradient-primary)',
        'gradient-hero': 'var(--gradient-hero)',
        'gradient-button': 'var(--gradient-button)',
      },
      keyframes: {
        "fade-in": {
          "0%": { opacity: "0" },
          "100%": { opacity: "1" },
        },
        "slide-up": {
          "0%": { transform: "translateY(20px)", opacity: "0" },
          "100%": { transform: "translateY(0)", opacity: "1" },
        },
        "slide-in-left": {
          "0%": { transform: "translateX(-20px)", opacity: "0" },
          "100%": { transform: "translateX(0)", opacity: "1" },
        },
        "float": {
          "0%, 100%": { transform: "translateY(0px)" },
          "50%": { transform: "translateY(-10px)" },
        },
        "gradient-shift": {
          "0%, 100%": { backgroundPosition: "0% 50%" },
          "50%": { backgroundPosition: "100% 50%" },
        },
        "ripple-effect": {
          "0%": { transform: "scale(0)", opacity: "1" },
          "100%": { transform: "scale(4)", opacity: "0" },
        },
        "particle-burst": {
          "0%": { transform: "translate(0, 0) scale(0)", opacity: "1" },
          "100%": { transform: "translate(var(--tx), var(--ty)) scale(1)", opacity: "0" },
        },
        "pulse-ring": {
          "0%, 100%": { transform: "scale(0.95)", boxShadow: "0 0 0 0 rgba(108, 63, 197, 0.7)" },
          "70%": { transform: "scale(1)", boxShadow: "0 0 0 10px rgba(108, 63, 197, 0)" },
        },
        "glow-pulse": {
          "0%, 100%": { boxShadow: "0 0 5px var(--accent-primary), 0 0 10px var(--accent-primary)" },
          "50%": { boxShadow: "0 0 20px var(--accent-primary), 0 0 30px var(--accent-primary)" },
        },
        "slide-in-up": {
          "0%": { transform: "translateY(20px)", opacity: "0" },
          "100%": { transform: "translateY(0)", opacity: "1" },
        },
        "count-up": {
          "0%": { opacity: "0", transform: "translateY(10px)" },
          "100%": { opacity: "1", transform: "translateY(0)" },
        },
        "particle-float": {
          "0%, 100%": { transform: "translate(0, 0) scale(1)" },
          "33%": { transform: "translate(30px, -30px) scale(1.1)" },
          "66%": { transform: "translate(-20px, 20px) scale(0.9)" },
        },
      },
      animation: {
        "fade-in": "fade-in 0.3s ease-out",
        "slide-up": "slide-up 0.4s ease-out",
        "slide-in-left": "slide-in-left 0.4s ease-out",
        "float": "float 6s ease-in-out infinite",
        "gradient-shift": "gradient-shift 3s ease infinite",
        "ripple-effect": "ripple-effect 0.6s linear",
        "particle-burst": "particle-burst 1s ease-out forwards",
        "pulse-ring": "pulse-ring 2s cubic-bezier(0.4, 0, 0.6, 1) infinite",
        "glow-pulse": "glow-pulse 2s ease-in-out infinite",
        "slide-in-up": "slide-in-up 0.5s ease-out forwards",
        "count-up": "count-up 0.4s ease-out forwards",
        "particle-float": "particle-float 8s ease-in-out infinite",
      },
    },
  },
  plugins: [require("tailwindcss-animate")],
} satisfies Config;

export default config;
