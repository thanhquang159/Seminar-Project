"""Mô hình POI v2, thêm bán kính geofence và ưu tiên audio.

V1 chỉ có 5 trường. V2 thêm `trigger_radius` và `audio_priority`
có giá trị mặc định nên dữ liệu cũ vẫn đọc được (tương thích ngược).
"""

from pydantic import BaseModel, Field

from app.limits import MAX_MO_TA, MAX_TEN


class Poi(BaseModel):
    """Một quán ăn trên bản đồ ở V2."""

    id: str | None = Field(default=None)
    # Ngưỡng khớp `admin_pois.PoiNhap` và `owner.SubmissionNhap` — cùng một quán
    # đi qua ba cửa mà khác ngưỡng thì dữ liệu từ cửa lỏ sẽ phá cửa chặt.
    name: str = Field(min_length=1, max_length=MAX_TEN)
    description: str = Field(default="", max_length=MAX_MO_TA)
    lat: float = Field(ge=-90, le=90)
    lng: float = Field(ge=-180, le=180)
    # Bán kính vòng geofence (m), validate chặt ở POI-010.
    trigger_radius: float = Field(default=30, ge=5, le=200)
    # Ưu tiên đọc khi nhiều quán cùng đủ điều kiện, số nhỏ đọc trước.
    audio_priority: int = Field(default=0, ge=0, le=100)
