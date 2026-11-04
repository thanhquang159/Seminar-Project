"""Adapter AI: mock cho dev, HTTP provider cho production, timeout 30s."""

import httpx

from app.config import settings

TIMEOUT_GIAY = 30


class NhaCungCap:
    async def viet_lai(self, mo_ta: str) -> str:
        raise NotImplementedError


class MockProvider(NhaCungCap):
    """Dev: không bịa nội dung mới, chỉ thêm tính từ tích cực, 200-300 từ giả lập."""

    async def viet_lai(self, mo_ta: str) -> str:
        return f"Quán ngon nức tiếng, {mo_ta} Hương vị đậm đà khó quên, không gian ấm cúng đáng thử."


class HttpProvider(NhaCungCap):
    """Provider HTTP chung (ProxyPal/Gemini-compatible), lỗi theo nhà cung cấp."""

    async def viet_lai(self, mo_ta: str) -> str:
        # SEC-013 (A04): thiếu URL thì báo lỗi cấu hình NGAY, đừng đi request với
        # URL rỗng rồi trả về cho client một lỗi httpx khó hiểu. Đây là lỗi đặt
        # sai biến môi trường, phải nói đúng tên biến chứ không nói "request
        # thiếu protocol".
        if not settings.ai_api_url:
            raise RuntimeError(
                "AI chưa cấu hình: đặt AI_API_URL (và AI_API_KEY) khi AI_PROVIDER=http"
            )
        try:
            async with httpx.AsyncClient(timeout=TIMEOUT_GIAY) as client:
                res = await client.post(
                    settings.ai_api_url,
                    headers={"Authorization": f"Bearer {settings.ai_api_key}"},
                    json={"prompt": f"Viết lại mô tả quán 200-300 từ, không bịa: {mo_ta}"},
                )
                res.raise_for_status()
                return str(res.json().get("text", ""))
        except httpx.TimeoutException:
            raise RuntimeError("AI quá 30 giây không trả lời") from None
        except httpx.HTTPError as exc:
            raise RuntimeError(f"AI lỗi: {exc}") from exc


def lay_provider() -> NhaCungCap:
    if settings.ai_provider == "mock":
        return MockProvider()
    return HttpProvider()
