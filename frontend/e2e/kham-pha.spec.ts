import { expect, test } from '@playwright/test'

// TEST-006 — luồng cơ bản: mở app → chọn ngôn ngữ → bản đồ hiện POI.
// Đây là "happy path" ngắn nhất để phát hiện app hỏng khiếu ngay ở CI, nên
// dùng selector theo nhãn người dùng thấy thay vì class CSS (đổi style không
// được làm vỡ test).

test.describe('Khám phá', () => {
  test('mở app thì có bản đồ và danh sách quán', async ({ page }) => {
    await page.goto('/')

    await expect(page.getByRole('heading', { name: 'Linh Ứng Guide' })).toBeVisible()
    await expect(page.locator('.map-frame')).toBeVisible()
    await expect(page.getByRole('heading', { name: 'Food spots' })).toBeVisible()
    await expect(page.getByRole('button', { name: 'English' })).toBeDisabled()
    // Seed 5 quán; danh sách phải đủ 5 để biết API và store đồng bộ.
    await expect(page.locator('.poi-btn')).toHaveCount(5)
  })

  test('đổi ngôn ngữ thì giao diện và nội dung POI cùng được dịch', async ({ page }) => {
    await page.goto('/')
    await expect(page.locator('.poi-btn')).toHaveCount(5)
    const dauTien = page.locator('.poi-btn').first()
    const tiengAnh = await dauTien.innerText()

    await page.getByRole('button', { name: 'Tiếng Việt' }).click()
    await expect(page.getByRole('heading', { name: 'Danh sách điểm ẩm thực' })).toBeVisible()
    await expect(dauTien).not.toHaveText(tiengAnh, { timeout: 15_000 })
    const tiengViet = await dauTien.innerText()

    await page.getByRole('button', { name: 'English' }).click()

    // Chờ nội dung POI về tiếng Anh thay vì chỉ kiểm tra nhãn giao diện.
    await expect(page.getByRole('heading', { name: 'Food spots' })).toBeVisible()
    await expect(dauTien).not.toHaveText(tiengViet, { timeout: 15_000 })
  })

  test('trên mobile hiển thị bộ chọn ngôn ngữ bo góc dạng gọn', async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 })
    await page.goto('/?tab=kham-pha')
    const languageSelect = page.locator('.mobile-language-select')

    await expect(languageSelect).toBeVisible()
    await expect(languageSelect).toHaveCSS('border-radius', '12px')
    await languageSelect.selectOption('vi')
    await expect(languageSelect).toHaveValue('vi')
    await expect(page.locator('.language-bar__scroll')).toBeHidden()
  })

  test('bấm vào một quán thì hiện chi tiết', async ({ page }) => {
    await page.goto('/')
    await page.locator('.poi-btn').first().click()
    await expect(page.getByRole('region', { name: 'Place details' })).toBeVisible()
  })

  test('trên mobile danh sách cuộn riêng còn bản đồ đứng yên', async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 })
    await page.goto('/?tab=kham-pha')
    const listColumn = page.locator('.kham-pha-grid__list-col')
    const mapColumn = page.locator('.kham-pha-grid__map-col')
    await expect(page.locator('.poi-btn')).toHaveCount(5)
    await expect(page.getByRole('button', { name: 'Toggle attribution' })).toHaveCount(0)
    await expect(page.locator('.maplibregl-ctrl-attrib')).toBeVisible()

    await expect
      .poll(() => listColumn.evaluate((element) => getComputedStyle(element).overflowY))
      .toBe('auto')

    const mapTop = await mapColumn.evaluate((element) => element.getBoundingClientRect().top)
    await listColumn.evaluate((element) => {
      element.scrollTop = 100
    })
    await expect.poll(() => listColumn.evaluate((element) => element.scrollTop)).toBeGreaterThan(0)
    await expect.poll(() => mapColumn.evaluate((element) => element.getBoundingClientRect().top)).toBe(mapTop)

    await page.locator('.poi-btn').first().click()
    await expect(page.getByRole('region', { name: 'Place details' })).toBeVisible()
    await expect(page.locator('.poi-list-section')).toBeVisible()
    await expect(page.locator('.poi-btn')).toHaveCount(5)

    await page.getByRole('button', { name: 'Close place details' }).click()
    await expect(page.locator('.poi-list-section')).toBeVisible()
  })

  test('không hiển thị thanh thay đổi kích thước bản đồ trên mobile', async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 })
    await page.goto('/?tab=kham-pha')
    await expect(page.locator('.mobile-map-resize-handle')).toHaveCount(0)
    const mapHeight = await page.locator('.kham-pha-grid__map-col').evaluate(
      (element) => element.getBoundingClientRect().height,
    )
    expect(mapHeight / 844).toBeGreaterThan(0.64)
    expect(mapHeight / 844).toBeLessThan(0.66)
  })

  test('mở POI trên mobile thu bản đồ còn 35% và đặt ảnh cạnh mô tả', async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 })
    await page.goto('/?tab=kham-pha')
    await page.locator('.poi-btn').first().click()

    const mapColumn = page.locator('.kham-pha-grid__map-col')
    const mapHeight = await mapColumn.evaluate((element) => element.getBoundingClientRect().height)
    expect(mapHeight / 844).toBeGreaterThan(0.32)
    expect(mapHeight / 844).toBeLessThan(0.38)

    const photo = await page.locator('.poi-gallery__main').boundingBox()
    const info = await page.locator('.poi-detail__info').boundingBox()
    const actions = await page.locator('.poi-detail__actions').boundingBox()
    if (photo === null || info === null || actions === null) {
      throw new Error('Không tìm thấy bố cục ảnh, mô tả hoặc nút nghe POI')
    }

    expect(info.x).toBeGreaterThan(photo.x)
    expect(Math.abs(info.y - photo.y)).toBeLessThan(12)
    expect(actions.y).toBeGreaterThan(Math.max(photo.y + photo.height, info.y + info.height) - 4)
    await expect(page.getByRole('button', { name: 'Listen to the audio guide' })).toBeVisible()
  })

  test('menu Tài khoản trên mobile chứa lối vào Chủ quán, Quản trị và Cài đặt', async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 })
    await page.goto('/?tab=kham-pha')
    const navigation = page.getByRole('navigation', { name: 'Main navigation' })

    await expect(navigation.getByRole('tab', { name: 'Explore' })).toBeVisible()
    await expect(navigation.getByRole('tab', { name: 'Offline packs' })).toBeVisible()
    await expect(navigation.getByRole('tab', { name: 'Restaurant owners' })).toBeHidden()

    await navigation.getByRole('button', { name: 'Account' }).click()
    await expect(navigation.getByRole('menuitem')).toHaveCount(3)
    await expect(navigation.getByRole('menuitem', { name: 'Restaurant owners' })).toBeVisible()
    await expect(navigation.getByRole('menuitem', { name: 'Administration' })).toBeVisible()
    await navigation.getByRole('menuitem', { name: 'Settings' }).click()

    await expect(navigation.getByRole('button', { name: 'Account' })).toHaveAttribute('aria-current', 'page')
    await expect(navigation.getByRole('menu')).toHaveCount(0)
  })

  test('không hiển thị nút Tài khoản trên laptop', async ({ page }) => {
    await page.setViewportSize({ width: 1280, height: 800 })
    await page.goto('/?tab=kham-pha')
    await expect(
      page.getByRole('navigation', { name: 'Main navigation' }).getByRole('button', { name: 'Account' }),
    ).toBeHidden()
  })

  test('mở trực tiếp link POI và đóng chi tiết thì trở về danh sách khám phá', async ({ page }) => {
    await page.goto('/?tab=kham-pha')
    await expect(page.locator('.poi-btn')).toHaveCount(5)
    await page.locator('.poi-btn').first().click()
    await expect(page).toHaveURL(/\/[^/?#]+$/)

    await page.reload()
    await expect(page.getByRole('region', { name: 'Place details' })).toBeVisible()

    await page.getByRole('button', { name: 'Close place details' }).click()
    await expect(page).toHaveURL(/\/\?tab=kham-pha$/)
    await expect(page.locator('.poi-btn')).toHaveCount(5)
  })

  test('mã POI không tồn tại sẽ chuyển về danh sách khám phá', async ({ page }) => {
    await page.goto('/poi-khong-ton-tai')
    await expect(page).toHaveURL(/\/\?tab=kham-pha$/)
    await expect(page.locator('.poi-btn')).toHaveCount(5)
  })

  test('nút quay lại và tiến tới đồng bộ chi tiết với URL', async ({ page }) => {
    await page.goto('/?tab=kham-pha')
    await expect(page.locator('.poi-btn')).toHaveCount(5)
    await page.locator('.poi-btn').first().click()
    await expect(page.getByRole('region', { name: 'Place details' })).toBeVisible()

    await page.goBack()
    await expect(page).toHaveURL(/\/\?tab=kham-pha$/)
    await expect(page.getByRole('region', { name: 'Place details' })).toHaveCount(0)

    await page.goForward()
    await expect(page.getByRole('region', { name: 'Place details' })).toBeVisible()
  })
})

// TEST-001 liên quan: hộp thoại consent phải xuất hiện và tôn trọng lựa chọn.
// Đặt ở đây vì nó là điều kiện tiên quyết cho mọi sự kiện analytics, và chỉ
// quan sát được qua UI thật.
test.describe('Consent', () => {
  test('mặc định hỏi consent, từ chối thì không gửi request analytics', async ({ page }) => {
    const goiAnalytics: string[] = []
    page.on('request', (r) => {
      if (r.url().includes('/analytics/collect')) goiAnalytics.push(r.url())
    })

    await page.goto('/')
    await expect(
      page.getByRole('dialog', { name: 'Xin phép chia sẻ dữ liệu ẩn danh' }),
    ).toBeVisible()

    await page.getByRole('button', { name: 'Không cho phép' }).click()
    await expect(page.getByRole('dialog')).toHaveCount(0)

    // Đợi qua nhịp heartbeat 20s là ràng buộc thật của ANA-001; ở đây chỉ cần
    // chắc là không có request nào ngay sau khi từ chối.
    await page.waitForTimeout(2000)
    expect(goiAnalytics).toHaveLength(0)
  })

  test('cho phép thì bật thu thập và nhớ lựa chọn qua lần tải sau', async ({ page }) => {
    await page.goto('/')
    // `exact: true` bắt buộc: "Cho phép" là chuỗi con của "Không cho phép",
    // nên không có nó thì selector khớp cả hai nút và Playwright báo
    // "strict mode violation".
    await page.getByRole('button', { name: 'Cho phép', exact: true }).click()
    await expect(page.getByText('đang bật')).toBeVisible()

    await page.reload()
    // Lựa chọn được nhớ: không hỏi lại, và vẫn hiện là đang bật.
    await expect(page.getByRole('dialog')).toHaveCount(0)
    await expect(page.getByText('đang bật')).toBeVisible()
  })
})