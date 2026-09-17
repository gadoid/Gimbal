/// <reference types="vite/client" />

// export {} 使本文件成为 module —— 下面的 declare module 才是"类型增强"
// (RouteMeta 补充字段)而不是整模块遮蔽。
export {}

declare module '*.vue' {
  import type { DefineComponent } from 'vue'
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const component: DefineComponent<{}, {}, any>
  export default component
}

declare module 'vue-router' {
  interface RouteMeta {
    requiresAuth?: boolean
    requiresAdmin?: boolean
    /** chrome 形态:'full' = 侧边栏(默认);'collapsed' = 收拢顶条 + 面包屑(编辑流页)。 */
    chromeMode?: 'full' | 'collapsed'
  }
}
