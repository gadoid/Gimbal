/** @type {import('tailwindcss').Config} */
// ESM 导出:package.json 是 "type": "module"
import tailwindcssAnimate from 'tailwindcss-animate'
/*
 * Signal 视觉体系 Tailwind 配置(重构方案 Phase 0)。
 *
 * Phase 3 起 preflight 已复位(双栈期结束,reset 全局生效);token
 * 全部录在这里,与 theme.css(Spec-1)并存。
 *
 * token 来源:D-palette / E-scale 原型图核录(2026-09-17)。
 * 未定项:
 * - accent 无 hover/pressed 分档(D-palette 未标)——按钮组件落地时补,走查(G-chrome)定稿;
 * - running 状态色 D-palette 未列(仅 signal 在线点 #22D3EE),沿用 status-colors.css;
 * - status 色已随批次 4 统一到 Signal(status-colors.css 与 token 同源)。
 */
export default {
  content: ['./index.html', './src/**/*.{vue,ts}'],
  theme: {
    extend: {
      colors: {
        // ── Signal 原子层(D-palette 核录,唯一 hex 真源)─────────
        // 冷灰中性阶
        signal: {
          sidebar: '#0B0E14',
          ink: '#10151C',
          canvas: '#F3F5F8',
          card: '#FFFFFF',
          line: '#E1E5EB',
          // 电光蓝主色
          DEFAULT: '#2F6FED',
          soft: '#E7EFFF',
          dot: '#22D3EE',
          // 状态色
          done: '#15803D',
          failed: '#DC2626',
          star: '#EAB308',
        },
        // 业务域 chip 独立分类色板(v3:与 accent/状态色彻底解耦)
        domain: {
          fin: '#7C5CBF',
          logi: '#2E8B9E',
          wms: '#8A7D6B',
          mall: '#B0568E',
          common: '#6B7280',
        },
        // ── shadcn-vue 语义层(变量值来自 tailwind.css :root,即 Signal token)──
        border: 'hsl(var(--border))',
        input: 'hsl(var(--input))',
        ring: 'hsl(var(--ring))',
        background: 'hsl(var(--background))',
        foreground: 'hsl(var(--foreground))',
        primary: {
          DEFAULT: 'hsl(var(--primary))',
          foreground: 'hsl(var(--primary-foreground))',
        },
        secondary: {
          DEFAULT: 'hsl(var(--secondary))',
          foreground: 'hsl(var(--secondary-foreground))',
        },
        destructive: {
          DEFAULT: 'hsl(var(--destructive))',
          foreground: 'hsl(var(--destructive-foreground))',
        },
        muted: {
          DEFAULT: 'hsl(var(--muted))',
          foreground: 'hsl(var(--muted-foreground))',
        },
        accent: {
          DEFAULT: 'hsl(var(--accent))',
          foreground: 'hsl(var(--accent-foreground))',
        },
        popover: {
          DEFAULT: 'hsl(var(--popover))',
          foreground: 'hsl(var(--popover-foreground))',
        },
        card: {
          DEFAULT: 'hsl(var(--card))',
          foreground: 'hsl(var(--card-foreground))',
        },
      },
      fontFamily: {
        // 与 theme.css --font-sans/--font-mono 同源;接入后 font-sans/font-mono
        // utility 与 token 联动(此前同值纯属巧合)。scoped CSS 层仍走
        // var(--font-mono, monospace)。
        sans: ['-apple-system', 'BlinkMacSystemFont', '"Segoe UI"', 'Roboto',
          '"Helvetica Neue"', 'Arial', '"Noto Sans"', 'sans-serif'],
        mono: ['var(--font-mono, monospace)'],
      },
      fontSize: {
        // E-scale 字号阶:字号/字重/行高(label/caption 同取 16 使 chip/pill
        // 基线对齐;micro 收编 10px 徽标档,字重 500,确需 400 显式 font-normal)
        'display-lg': ['26px', { fontWeight: '700', lineHeight: '34px' }],
        display: ['22px', { fontWeight: '600', lineHeight: '30px' }],
        heading: ['14px', { fontWeight: '600', lineHeight: '20px' }],
        body: ['13px', { fontWeight: '400', lineHeight: '18px' }],
        label: ['12px', { fontWeight: '500', lineHeight: '16px' }],
        caption: ['11px', { fontWeight: '400', lineHeight: '16px' }],
        micro: ['10px', { fontWeight: '500', lineHeight: '14px' }],
      },
      borderRadius: {
        // E-scale 圆角阶:3 卡片/代码 · 4 chip/徽标 · 6 表单/表格 · 8 空状态 · 10 主卡片
        none: '0',
        sm: '3px',
        chip: '4px',
        field: '6px',
        empty: '8px',
        card: '10px',
        full: '9999px',
        // shadcn-vue 组件消费的语义圆角(lg=8/md=6/sm=4,由 --radius 推导)
        lg: 'var(--radius)',
        md: 'calc(var(--radius) - 2px)',
        DEFAULT: 'calc(var(--radius) - 2px)',
      },
      // 间距沿用 Tailwind 默认 4px 网格(4/8/12/.../32),与 E-scale 一致,不重录
      boxShadow: {
        // 双阴影语义;数值 E-scale 未标,暂定值,组件走查(G-chrome)时定稿
        'sig-hover': '0 1px 2px rgba(16, 21, 28, 0.06)',
        'sig-float': '0 8px 24px rgba(16, 21, 28, 0.12)',
      },
    },
  },
  plugins: [tailwindcssAnimate],
}
