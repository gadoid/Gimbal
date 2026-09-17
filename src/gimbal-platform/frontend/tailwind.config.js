/** @type {import('tailwindcss').Config} */
// ESM 导出:package.json 是 "type": "module"
/*
 * Signal 视觉体系 Tailwind 配置(重构方案 Phase 0)。
 *
 * 双栈共存关键约束:
 * - `corePlugins.preflight: false`:关闭全局 reset,Tailwind 只作 utility 层,
 *   不污染尚未迁移的 Element Plus 页面(方案 §3 Phase 0)。
 * - token 全部录在这里,不零散写 hex;与 theme.css(Spec-1)并存,
 *   页面逐批迁移逐批切换。
 *
 * token 来源:D-palette / E-scale 原型图核录(2026-09-17)。
 * 未定项:
 * - accent 无 hover/pressed 分档(D-palette 未标)——按钮组件落地时补,走查(G-chrome)定稿;
 * - running 状态色 D-palette 未列(仅 signal 在线点 #22D3EE),沿用 status-colors.css;
 * - status 色与现状 status-colors.css(done #22c55e vs Signal #15803D)不同,
 *   批次 4 迁移执行历史时统一到 Signal,此前不动。
 */
export default {
  content: ['./index.html', './src/**/*.{vue,ts}'],
  corePlugins: {
    // 双栈隔离:不输出 preflight reset(见文件头注释)
    preflight: false,
  },
  theme: {
    extend: {
      colors: {
        // 冷灰中性阶(D-palette)
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
      },
      fontSize: {
        // E-scale 字号阶:字号/字重(行高原型未标,先按 1.5 倍近邻取值)
        'display-lg': ['26px', { fontWeight: '700' }],
        display: ['22px', { fontWeight: '600' }],
        heading: ['14px', { fontWeight: '600' }],
        body: ['13px', { fontWeight: '400' }],
        label: ['12px', { fontWeight: '500' }],
        caption: ['11px', { fontWeight: '400' }],
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
      },
      // 间距沿用 Tailwind 默认 4px 网格(4/8/12/.../32),与 E-scale 一致,不重录
      boxShadow: {
        // 双阴影语义;数值 E-scale 未标,暂定值,组件走查(G-chrome)时定稿
        'sig-hover': '0 1px 2px rgba(16, 21, 28, 0.06)',
        'sig-float': '0 8px 24px rgba(16, 21, 28, 0.12)',
      },
    },
  },
  plugins: [],
}
