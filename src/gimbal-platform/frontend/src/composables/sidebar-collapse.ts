// sidebar-collapse.ts — 侧边栏折叠态的单一真源。
// Sidebar( rail 宽度/图标态)与 App.vue(内容区让位宽度)两地消费,
// 模块级 ref 保证同帧一致;localStorage 持久化,刷新后保持折叠。
import { ref } from 'vue'

const STORAGE_KEY = 'chrome.sidebar.collapsed:v1'

const collapsed = ref(localStorage.getItem(STORAGE_KEY) === '1')

export function useSidebarCollapse() {
  function toggle(): void {
    collapsed.value = !collapsed.value
    localStorage.setItem(STORAGE_KEY, collapsed.value ? '1' : '0')
  }

  return { collapsed, toggle }
}
