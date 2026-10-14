/**
 * Component regression tests for the image re-upload fix (final acceptance).
 *
 * These mount the REAL ImageUploader component and drive the native file
 * input, covering the operation sequences reported by the user:
 *   A. upload -> clear -> upload the same file -> works
 *   B. upload file1 -> re-select file2 -> result corresponds to file2
 *   C. upload -> clear -> upload a different file -> works
 *   D. continuous different files -> no stale preview / stuck state
 *   E. rejected file -> user can still clear and re-upload
 */
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import ImageUploader from '../src/components/ImageUploader.vue'

// jsdom has no object-URL implementation.
beforeEach(() => {
  global.URL.createObjectURL = vi.fn(() => 'blob:mock-url')
  global.URL.revokeObjectURL = vi.fn()
})

function makeJpeg(name) {
  const bytes = new Uint8Array([0xff, 0xd8, 0xff, 0xe0, 0, 1, 2, 3])
  return new File([bytes], name, { type: 'image/jpeg' })
}

function makeBmp(name) {
  const bytes = new Uint8Array([0x42, 0x4d, 0, 1, 2, 3])
  return new File([bytes], name, { type: 'image/bmp' })
}

function mountUploader() {
  return mount(ImageUploader, {
    global: { plugins: [ElementPlus] },
    attachTo: document.body
  })
}

async function selectFile(wrapper, file) {
  const input = wrapper.find('input[type="file"]')
  expect(input.exists()).toBe(true)
  Object.defineProperty(input.element, 'files', {
    value: [file],
    configurable: true
  })
  await input.trigger('change')
  await flushPromises()
}

function previewImage(wrapper) {
  return wrapper.find('img.preview-image')
}

function actionButton(wrapper, text) {
  return wrapper.findAll('button').find((btn) => btn.text() === text)
}

describe('ImageUploader re-upload regression', () => {
  it('A: upload -> clear -> upload the SAME file again -> works', async () => {
    const wrapper = mountUploader()
    const file1 = makeJpeg('pet.jpg')

    await selectFile(wrapper, file1)
    expect(wrapper.emitted('select')).toHaveLength(1)
    expect(previewImage(wrapper).exists()).toBe(true)

    // clear
    await actionButton(wrapper, '移除图片').trigger('click')
    expect(wrapper.emitted('clear')).toHaveLength(1)
    expect(previewImage(wrapper).exists()).toBe(false)

    // re-select the same file: must work without a page refresh
    await selectFile(wrapper, file1)
    expect(wrapper.emitted('select')).toHaveLength(2)
    expect(previewImage(wrapper).exists()).toBe(true)

    wrapper.unmount()
  })

  it('B: upload file1 -> re-select file2 -> selection corresponds to file2', async () => {
    const wrapper = mountUploader()
    await selectFile(wrapper, makeJpeg('first.jpg'))
    await selectFile(wrapper, makeJpeg('second.jpg'))

    const events = wrapper.emitted('select')
    expect(events).toHaveLength(2)
    expect(events[1][0].name).toBe('second.jpg')
    expect(wrapper.text()).toContain('second.jpg')

    wrapper.unmount()
  })

  it('C: upload -> clear -> upload a different file -> works', async () => {
    const wrapper = mountUploader()
    await selectFile(wrapper, makeJpeg('one.jpg'))
    await actionButton(wrapper, '移除图片').trigger('click')
    expect(previewImage(wrapper).exists()).toBe(false)

    await selectFile(wrapper, makeJpeg('two.png'))
    expect(wrapper.emitted('select')).toHaveLength(2)
    expect(previewImage(wrapper).exists()).toBe(true)
    expect(wrapper.text()).toContain('two.png')

    wrapper.unmount()
  })

  it('D: continuous different files -> single fresh preview, no stale state', async () => {
    const wrapper = mountUploader()
    await selectFile(wrapper, makeJpeg('a.jpg'))
    await selectFile(wrapper, makeJpeg('b.jpg'))
    await selectFile(wrapper, makeJpeg('c.jpg'))

    expect(wrapper.findAll('img.preview-image')).toHaveLength(1)
    expect(wrapper.text()).toContain('c.jpg')
    expect(wrapper.text()).not.toContain('a.jpg')

    wrapper.unmount()
  })

  it('E: rejected file -> previous selection kept, picker still usable', async () => {
    const wrapper = mountUploader()
    await selectFile(wrapper, makeJpeg('good.jpg'))
    expect(previewImage(wrapper).exists()).toBe(true)

    // rejected file must not destroy the current selection...
    await selectFile(wrapper, makeBmp('bad.bmp'))
    expect(previewImage(wrapper).exists()).toBe(true)
    expect(wrapper.emitted('select')).toHaveLength(1)

    // ...and the picker remains usable afterwards
    await selectFile(wrapper, makeJpeg('next.jpg'))
    expect(wrapper.emitted('select')).toHaveLength(2)
    expect(wrapper.text()).toContain('next.jpg')

    wrapper.unmount()
  })

  it('resets the native input value so the same file can fire change again', async () => {
    const wrapper = mountUploader()
    const file = makeJpeg('same.jpg')
    await selectFile(wrapper, file)

    const input = wrapper.find('input[type="file"]')
    expect(input.element.value).toBe('')

    wrapper.unmount()
  })

  it('clearSelection() exposed method clears preview and emits clear', async () => {
    const wrapper = mountUploader()
    await selectFile(wrapper, makeJpeg('x.jpg'))
    expect(previewImage(wrapper).exists()).toBe(true)

    wrapper.vm.clearSelection()
    await flushPromises()
    expect(previewImage(wrapper).exists()).toBe(false)
    expect(wrapper.emitted('clear')).toHaveLength(1)

    wrapper.unmount()
  })

  it('re-select button keeps the picker usable', async () => {
    const wrapper = mountUploader()
    await selectFile(wrapper, makeJpeg('r1.jpg'))

    const reselect = actionButton(wrapper, '重新选择')
    expect(reselect.exists()).toBe(true)
    await reselect.trigger('click')
    await flushPromises()

    // after re-select trigger, selecting a file still works
    await selectFile(wrapper, makeJpeg('r2.jpg'))
    expect(wrapper.emitted('select')).toHaveLength(2)

    wrapper.unmount()
  })
})
