import { expect, test } from '@playwright/test'

// TEST-008 — luồng chủ quán: đăng ký → duyệt → gửi quán → nhận thông báo.
//
// Đây là luồng dài nhất của ứng dụng nên nó đi qua cả hai cổng đăng nhập riêng:
// Owner (khách) và Admin (vận hành). Nếu chỉ test từng đầu mối riêng lẻ thì hỏng "đứt
// giữa đường" — ví dụ owner gửi được quán nhưng admin không thấy đơn — sẽ lọt qua.

const CHU_QUAN = 'chuquan_e2e'
const MAT_KHAU = 'e2e123456'
const TEN_QUAN = 'Quán mới E2E'

test.describe('Luồng chủ quán', () => {
  test('đăng ký, được duyệt, gửi quán và nhận thông báo', async ({ page }) => {
    // --- 1. Khách đăng ký làm chủ quán ---
    await page.goto('/owner/login')
    await page.getByRole('button', { name: 'Đăng ký chủ quán' }).click()
    await page.getByLabel('Tên đăng nhập').fill(CHU_QUAN)
    await page.getByLabel('Mật khẩu').fill(MAT_KHAU)
    await page.getByLabel('Số Căn cước công dân (CCCD)').fill('123456789012')
    await page.getByRole('button', { name: 'Tạo tài khoản chủ quán' }).click()
    await expect(page.getByText('Tài khoản chờ duyệt, chưa gửi được quán.')).toBeVisible()

    // --- 2. Chuyển sang trang Admin và duyệt tài khoản ---
    await page.goto('/admin/login')
    await page.getByLabel('Email hoặc tên đăng nhập').fill('e2e-admin')
    await page.getByLabel('Mật khẩu').fill(MAT_KHAU)
    await page.getByRole('button', { name: 'Đăng nhập quản trị' }).click()

    await expect(page).toHaveURL(/\/admin$/)
    await page.getByRole('link', { name: 'Duyệt chủ quán' }).click()
    await expect(page).toHaveURL(/\/admin\/approvals$/)
    await page.reload()
    await expect(page.getByRole('heading', { name: /Kiểm duyệt chủ quán/ })).toBeVisible()
    const dong = page.locator('tr', { hasText: CHU_QUAN })
    await expect(dong).toHaveCount(1)
    await dong.getByRole('button', { name: 'Duyệt', exact: true }).click()
    // Đơn biến mất khỏi hàng đợi sau khi duyệt.
    await expect(page.locator('tr', { hasText: CHU_QUAN })).toHaveCount(0)

    // --- 3. Chuyển sang trang Chủ quán, đăng nhập và gửi quán ---
    await page.goto('/owner/login')
    await page.getByLabel('Tên đăng nhập').fill(CHU_QUAN)
    await page.getByLabel('Mật khẩu').fill(MAT_KHAU)
    await page.getByRole('button', { name: 'Đăng nhập', exact: true }).click()
    await expect(page).toHaveURL(/\/owner$/)
    await page.reload()
    await page.getByPlaceholder('Tên quán').fill(TEN_QUAN)
    await page.getByPlaceholder('Mô tả').fill('Quán ngon, giá hợp lý.')
    await page.getByRole('button', { name: 'Gửi', exact: true }).click()

    // --- 4. Admin duyệt quán, chủ quán nhận thông báo ---
    await page.goto('/admin/login')
    await page.getByLabel('Email hoặc tên đăng nhập').fill('e2e-admin')
    await page.getByLabel('Mật khẩu').fill(MAT_KHAU)
    await page.getByRole('button', { name: 'Đăng nhập quản trị' }).click()
    await expect(page).toHaveURL(/\/admin$/)
    await page.getByRole('link', { name: 'Duyệt chủ quán' }).click()
    await expect(page.getByRole('heading', { name: /Kiểm duyệt chủ quán/ })).toBeVisible()
    const dongQuan = page.locator('tr', { hasText: TEN_QUAN })
    await expect(dongQuan).toHaveCount(1, { timeout: 15_000 })
    await dongQuan.getByRole('button', { name: 'Duyệt quán' }).click()

    await page.goto('/owner/login')
    await page.getByLabel('Tên đăng nhập').fill(CHU_QUAN)
    await page.getByLabel('Mật khẩu').fill(MAT_KHAU)
    await page.getByRole('button', { name: 'Đăng nhập', exact: true }).click()
    await expect(page.getByText(/đã được duyệt/)).toBeVisible({ timeout: 15_000 })
    await page.getByRole('link', { name: 'Trạng thái gửi duyệt' }).click()
    await expect(page).toHaveURL(/\/owner\/history$/)
    await page.goBack()
    await expect(page).toHaveURL(/\/owner$/)
    await page.goForward()
    await expect(page).toHaveURL(/\/owner\/history$/)
    await page.reload()
    const submission = page.locator('tr', { hasText: TEN_QUAN })
    await expect(submission).toHaveCount(1)
    await expect(submission).toContainText('Đã được duyệt')
    await page.getByRole('link', { name: 'Thông báo' }).click()
    const danhDauDaDoc = page.getByRole('button', { name: 'Đánh dấu đã đọc' })
    for (let i = 0; i < 5 && await danhDauDaDoc.count() > 0; i += 1) {
      await danhDauDaDoc.first().click()
    }
    await expect(danhDauDaDoc).toHaveCount(0)
  })

  test('chủ quán chưa được duyệt thì không gửi được quán', async ({ page }) => {
    // Ranh giới quan trọng: nút "Gửi" phải bị chặn ở server (403), không chỉ ẩn nút.
    const chuaDuyet = 'chuquan_chua_duyet'
    await page.goto('/owner/login')
    await page.getByRole('button', { name: 'Đăng ký chủ quán' }).click()
    await page.getByLabel('Tên đăng nhập').fill(chuaDuyet)
    await page.getByLabel('Mật khẩu').fill(MAT_KHAU)
    await page.getByLabel('Số Căn cước công dân (CCCD)').fill('987654321098')
    await page.getByRole('button', { name: 'Tạo tài khoản chủ quán' }).click()
    await expect(page.getByText('Tài khoản chờ duyệt, chưa gửi được quán.')).toBeVisible()
    await expect(page.getByRole('button', { name: 'Gửi', exact: true })).toBeDisabled()
  })
})