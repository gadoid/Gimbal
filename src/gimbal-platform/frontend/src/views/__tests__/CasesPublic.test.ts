/**
 * Regression tests for CasesPublic.vue — the two bugs we hit:
 *
 * 1. ⭐ was a `<span>` (decorative); must be a clickable `<button>` so users
 *    can favorite without opening the dropdown.
 *
 * 2. ⋯ dropdown was wrapped in `<el-dropdown @click.stop>` which didn't stop
 *    click bubbling to the row-click handler. After the fix, the inner
 *    `<button @click.stop>` keeps row-click from firing when ⋯ is clicked.
 */
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createMemoryHistory, createRouter } from 'vue-router'
import ElementPlus from 'element-plus'
import CasesPublic from '@/views/CasesPublic.vue'
import { useCasesStore } from '@/stores/cases'
import { useAuthStore } from '@/stores/auth'

function makeRouter() {
  return createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/cases/public', component: { template: '<div/>' } },
      { path: '/cases/:caseId/config', component: { template: '<div/>' } },
    ],
  })
}

const fakeCase = {
  case_id: 'sc_demo',
  name: 'Demo Case',
  module: 'demo',
  description: '',
  visibility: 'public',
  owner_id: null,
  audited: true,
  file_path: 'data/public/sc_demo.json',
  updated_at: '2026-07-13T00:00:00',
  tags: ['smoke'],
  priority: 1,
  author: 'alice',
  favorited_by_me: false,
  copied_by_me: false,
}

describe('CasesPublic', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('renders the favorite star as a clickable button', async () => {
    const casesStore = useCasesStore()
    casesStore.publicLibrary = [fakeCase]
    casesStore.toggleFavorite = vi.fn().mockResolvedValue(true)

    const router = makeRouter()
    router.push('/cases/public')
    await router.isReady()

    const w = mount(CasesPublic, {
      global: { plugins: [router, ElementPlus] },
    })
    await flushPromises()

    const star = w.find('button.favorite-button')
    expect(star.exists()).toBe(true)
    expect(star.text()).toBe('☆')

    await star.trigger('click')
    expect(casesStore.toggleFavorite).toHaveBeenCalledWith('sc_demo')
  })

  it('star shows ★ + active class when favorited', async () => {
    const casesStore = useCasesStore()
    casesStore.publicLibrary = [{ ...fakeCase, favorited_by_me: true }]

    const router = makeRouter()
    router.push('/cases/public')
    await router.isReady()

    const w = mount(CasesPublic, {
      global: { plugins: [router, ElementPlus] },
    })
    await flushPromises()

    const star = w.find('button.favorite-button')
    expect(star.text()).toBe('★')
    expect(star.classes()).toContain('active')
  })

  it('clicking the ⋯ button does not navigate to detail', async () => {
    const casesStore = useCasesStore()
    casesStore.publicLibrary = [fakeCase]
    const authStore = useAuthStore()
    authStore.currentUser = { id: 1, username: 'alice', is_admin: true } as never

    const router = makeRouter()
    router.push('/cases/public')
    await router.isReady()

    const w = mount(CasesPublic, {
      global: { plugins: [router, ElementPlus] },
      attachTo: document.body,
    })
    await flushPromises()

    const more = w.find('button.more-button')
    expect(more.exists()).toBe(true)
    await more.trigger('click')
    await flushPromises()

    // The bug fix's contract: ⋯ click must NOT bubble to row-click, so URL
    // stays on /cases/public. (We don't assert the dropdown actually
    // appears in jsdom — el-dropdown uses Teleport which jsdom renders
    // outside the wrapper subtree.)
    expect(router.currentRoute.value.path).toBe('/cases/public')
  })

  it('clicking the case name navigates to detail', async () => {
    const casesStore = useCasesStore()
    casesStore.publicLibrary = [fakeCase]

    const router = makeRouter()
    router.push('/cases/public')
    await router.isReady()

    const w = mount(CasesPublic, {
      global: { plugins: [router, ElementPlus] },
    })
    await flushPromises()

    const name = w.find('button.case-name')
    expect(name.exists()).toBe(true)
    await name.trigger('click')
    await flushPromises()
    expect(router.currentRoute.value.path).toBe(
      `/cases/${encodeURIComponent('sc_demo')}/config`,
    )
  })
})