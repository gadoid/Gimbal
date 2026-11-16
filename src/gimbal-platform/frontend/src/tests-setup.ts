/**
 * tests-setup.ts — vitest 全局 setup。
 *
 * jsdom 未实现 Pointer Capture API,reka-ui 的 SelectTrigger 等
 * 挂 pointerdown 处理时会调 hasPointerCapture/setPointerCapture —
 * 在 jsdom 里直接交互下拉会抛 TypeError。补 no-op stub 让
 * pointer 路径可测(选中逻辑不受影响,捕获语义 jsdom 本就无)。
 * lib.dom 已声明这三个签名 → 覆盖赋值,不走 ts-expect-error。
 */
import { vi } from 'vitest'

// jsdom 运行时缺实现(lib.dom 类型在,实例方法不在)
Element.prototype.hasPointerCapture = (() => false) as typeof Element.prototype.hasPointerCapture
Element.prototype.setPointerCapture = vi.fn() as unknown as typeof Element.prototype.setPointerCapture
Element.prototype.releasePointerCapture = vi.fn() as unknown as typeof Element.prototype.releasePointerCapture
