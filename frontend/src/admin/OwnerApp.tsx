import { useCallback, useEffect, useRef, useState } from "react";
import { api, apiText } from "./api";
import { apiErrorMessage } from "./apiErrors";
import { useOwnerNotifications } from "./useOwnerNotifications";
import PortalDashboard, { type PortalDashboardItem } from "./PortalDashboard";
import OwnerMenuManagement from "./OwnerMenuManagement";
import OwnerPoiQrCodes from "./OwnerPoiQrCodes";
import { layUrlAnh } from "../components/imageUtils";
import {
  getOwnerPortalPage,
  getPortalPath,
  isStaleLoginSessionCheck,
  navigateToPath,
} from "./portalRoutes";

type OwnerAuthMode = "login" | "register";
type OwnerDashboardTab =
  | "submission"
  | "history"
  | "places"
  | "qr"
  | "menu"
  | "notifications";

interface OwnerSubmission {
  id: string;
  poi_id: string | null;
  data: Record<string, unknown>;
  status: string;
  submission_type?: "create" | "update";
  created_at: string | null;
  admin_note: string | null;
}

interface OwnerPoi {
  id: string;
  name: string;
  description: string;
  address_line: string;
  category?: string;
  source_language?: string;
  lat: number;
  lng: number;
  trigger_radius: number;
  audio_url: string | null;
  publication_status: string;
  is_active: boolean;
  pending_images: string[] | null;
}

interface MenuItemDraft {
  name: string;
  description: string;
  price: string;
}

export default function OwnerApp() {
  const [user, setUser] = useState<string | null>(null);
  const [authMode, setAuthMode] = useState<OwnerAuthMode>("login");
  const [dashboardTab, setDashboardTab] = useState<OwnerDashboardTab>(
    () => getOwnerPortalPage(window.location.pathname) ?? "submission",
  );
  const [checkingSession, setCheckingSession] = useState(true);
  const [ten, setTen] = useState("");
  const [matKhau, setMatKhau] = useState("");
  const [cccd, setCccd] = useState("");
  const [loi, setLoi] = useState("");
  const {
    status: trangThai,
    adminNote,
    notifications: thongBao,
    error: loiThongBao,
    markRead: danhDauDaDoc,
  } = useOwnerNotifications(user);
  const [tenQuan, setTenQuan] = useState("");
  const [moTa, setMoTa] = useState("");
  const [diaChi, setDiaChi] = useState("");
  const [viDo, setViDo] = useState("");
  const [kinhDo, setKinhDo] = useState("");
  const [danhMuc, setDanhMuc] = useState("other");
  const [ngonNguNguon, setNgonNguNguon] = useState("vi");
  const [banKinh, setBanKinh] = useState("30");
  const [hinhAnhMoi, setHinhAnhMoi] = useState<File[]>([]);
  const [tenThucDon, setTenThucDon] = useState("Menu chính");
  const [moTaThucDon, setMoTaThucDon] = useState("");
  const [monTrongThucDon, setMonTrongThucDon] = useState<MenuItemDraft[]>([
    { name: "", description: "", price: "" },
  ]);
  const [poiDangSua, setPoiDangSua] = useState("");
  const [dangXuLyAI, setDangXuLyAI] = useState(false);
  const [goiYAI, setGoiYAI] = useState("");
  const [thongBaoGui, setThongBaoGui] = useState("");
  const [lichSu, setLichSu] = useState<OwnerSubmission[]>([]);
  const [trangThaiLichSu, setTrangThaiLichSu] = useState<
    "loading" | "ready" | "error"
  >("loading");
  const historyRequest = useRef(0);
  const [dangGui, setDangGui] = useState(false);
  const [poisCuaToi, setPoisCuaToi] = useState<OwnerPoi[]>([]);

  const taiLichSu = useCallback(
    async (isActive: () => boolean = () => true) => {
      const request = ++historyRequest.current;
      setTrangThaiLichSu("loading");
      try {
        const submissions = await api<OwnerSubmission[]>(
          "/owner/submissions/mine",
        );
        if (!isActive() || request !== historyRequest.current) return;
        setLichSu(submissions);
        setTrangThaiLichSu("ready");
      } catch {
        if (isActive() && request === historyRequest.current)
          setTrangThaiLichSu("error");
      }
    },
    [],
  );

  useEffect(() => {
    if (!user || (trangThai !== "approved" && trangThai !== "admin")) return;
    let active = true;
    const load = async () => {
      await taiLichSu(() => active);
      try {
        const pois = await api<OwnerPoi[]>("/owner/pois");
        if (!active) return;
        setPoisCuaToi(pois);
      } catch {
        if (active)
          setLoi(
            "Đăng nhập được nhưng chưa tải được thông tin Chủ quán. Hãy tải lại trang.",
          );
      }
    };
    void load();
    return () => {
      active = false;
    };
  }, [user, trangThai, taiLichSu]);

  useEffect(() => {
    if (!user || (trangThai !== "approved" && trangThai !== "admin")) return;
    let active = true;
    const refresh = async () => {
      if (dashboardTab === "history") await taiLichSu(() => active);
      if (
        dashboardTab === "places" ||
        dashboardTab === "menu" ||
        dashboardTab === "qr"
      ) {
        try {
          const pois = await api<OwnerPoi[]>("/owner/pois");
          if (active) setPoisCuaToi(pois);
        } catch {
          if (active)
            setLoi("Không tải được danh sách địa điểm của bạn. Hãy thử lại.");
        }
      }
    };
    void refresh();
    window.addEventListener("focus", refresh);
    return () => {
      active = false;
      window.removeEventListener("focus", refresh);
    };
  }, [dashboardTab, trangThai, user, taiLichSu]);

  useEffect(() => {
    let mounted = true;
    const syncRoute = () => {
      const page = getOwnerPortalPage(window.location.pathname);
      if (page !== null) {
        setDashboardTab(page);
      } else if (
        window.location.pathname.startsWith("/owner/") &&
        window.location.pathname !== "/owner/login"
      ) {
        navigateToPath("/owner", true);
      }
    };
    window.addEventListener("popstate", syncRoute);
    syncRoute();

    const restoreSession = async () => {
      const pathAtStart = window.location.pathname;
      try {
        const me = await api<{ username: string }>("/owner/auth/me");
        if (!mounted) return;
        if (
          isStaleLoginSessionCheck(
            pathAtStart,
            window.location.pathname,
            "/owner/login",
          )
        )
          return;
        setUser(me.username);
        if (mounted && window.location.pathname === "/owner/login") {
          navigateToPath("/owner", true);
        }
      } catch {
        if (!mounted) return;
        if (
          isStaleLoginSessionCheck(
            pathAtStart,
            window.location.pathname,
            "/owner/login",
          )
        )
          return;
        setUser(null);
        if (window.location.pathname !== "/owner/login") {
          navigateToPath("/owner/login", true);
        }
      } finally {
        if (mounted) setCheckingSession(false);
      }
    };
    void restoreSession();

    return () => {
      mounted = false;
      window.removeEventListener("popstate", syncRoute);
    };
  }, []);

  const dangNhap = async () => {
    setLoi("");
    try {
      const res = await apiText("/owner/auth/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username: ten, password: matKhau }),
      });
      if (!res.ok) {
        setLoi("Sai tên đăng nhập hoặc mật khẩu");
        return;
      }
      setUser(ten);
      setMatKhau("");
      navigateToPath("/owner");
    } catch {
      setLoi("Không kết nối được máy chủ. Hãy kiểm tra backend và thử lại.");
    }
  };

  const dangXuat = async () => {
    try {
      const response = await apiText("/admin/auth/logout", { method: "POST" });
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      setUser(null);
      setLichSu([]);
      setPoisCuaToi([]);
      navigateToPath("/owner/login", true);
    } catch {
      setLoi("Không thể đăng xuất. Vui lòng thử lại.");
    }
  };

  const dangKy = async () => {
    setLoi("");
    if (!ten.trim() || !matKhau.trim() || !cccd.trim()) {
      setLoi("Vui lòng điền đầy đủ Tên đăng nhập, Mật khẩu và số CCCD");
      return;
    }
    const res = await apiText("/owner/register", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username: ten, password: matKhau, cccd }),
    });
    if (!res.ok) {
      const payload: unknown = await res.json().catch(() => null);
      const detail =
        typeof payload === "object" && payload !== null && "detail" in payload
          ? payload.detail
          : null;
      setLoi(
        typeof detail === "string"
          ? `Đăng ký thất bại: ${detail}`
          : `Đăng ký thất bại (HTTP ${res.status})`,
      );
      return;
    }

    setLoi("");
    setAuthMode("login");
    setCccd("");
    await dangNhap();
  };

  const aiAdvisor = async () => {
    setLoi("");
    setGoiYAI("");
    setDangXuLyAI(true);
    try {
      const goi = await api<{ text: string }>("/ai/enhance-description", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text: moTa }),
      });
      setMoTa(goi.text);
      setGoiYAI(
        "AI đã đề xuất bản mô tả. Bạn hãy xem lại và chỉnh sửa trước khi gửi.",
      );
    } catch {
      setLoi("AI bận hoặc hết lượt hôm nay");
    } finally {
      setDangXuLyAI(false);
    }
  };

  const guiQuan = async () => {
    if (dangGui) return;
    setLoi("");
    setThongBaoGui("");
    if (!tenQuan.trim()) {
      setLoi("Vui lòng nhập tên quán ăn");
      return;
    }
    const lat = Number(viDo);
    const lng = Number(kinhDo);
    if (!diaChi.trim()) {
      setLoi("Vui lòng nhập địa chỉ quán");
      return;
    }
    if (!viDo.trim() || !Number.isFinite(lat) || lat < -90 || lat > 90) {
      setLoi("Vui lòng nhập vĩ độ hợp lệ trong khoảng -90 đến 90");
      return;
    }
    if (!kinhDo.trim() || !Number.isFinite(lng) || lng < -180 || lng > 180) {
      setLoi("Vui lòng nhập kinh độ hợp lệ trong khoảng -180 đến 180");
      return;
    }
    const triggerRadius = Number(banKinh);
    if (
      !banKinh.trim() ||
      !Number.isFinite(triggerRadius) ||
      triggerRadius < 5 ||
      triggerRadius > 200
    ) {
      setLoi("Bán kính kích hoạt phải từ 5 đến 200 mét");
      return;
    }
    if (hinhAnhMoi.length > 8) {
      setLoi("Mỗi POI tối đa 8 hình ảnh");
      return;
    }
    if (hinhAnhMoi.some((file) => file.size > 5 * 1024 * 1024)) {
      setLoi("Mỗi hình ảnh tối đa 5 MB");
      return;
    }
    if (
      hinhAnhMoi.some(
        (file) =>
          !["image/jpeg", "image/png", "image/webp"].includes(file.type),
      )
    ) {
      setLoi("Chỉ hỗ trợ hình ảnh JPEG, PNG hoặc WebP");
      return;
    }
    const menuItems = monTrongThucDon
      .filter((item) => item.name.trim() !== "")
      .map((item) => ({
        name: item.name.trim(),
        description: item.description.trim(),
        price: item.price.trim() ? Number(item.price) : null,
      }));
    if (
      menuItems.some(
        (item) =>
          item.price !== null &&
          (!Number.isFinite(item.price) || item.price < 0),
      )
    ) {
      setLoi("Giá món ăn phải là số không âm");
      return;
    }
    setDangGui(true);
    try {
      const response = await apiText("/owner/submissions", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          ...(poiDangSua ? { poi_id: poiDangSua } : {}),
          name: tenQuan,
          description: moTa,
          address_line: diaChi.trim(),
          lat,
          lng,
          category: danhMuc,
          source_language: ngonNguNguon,
          trigger_radius: triggerRadius,
          ...(!poiDangSua && menuItems.length > 0
            ? {
                menu: {
                  name: tenThucDon.trim() || "Menu chính",
                  description: moTaThucDon.trim(),
                  items: menuItems,
                },
              }
            : {}),
        }),
      });
      if (!response.ok) {
        setLoi(await apiErrorMessage(response, "Gửi quán thất bại"));
        return;
      }
      const submitted =
        typeof (response as Response & { json?: () => Promise<unknown> })
          .json === "function"
          ? ((await (response as Response).json()) as {
              submission_id: string;
              collision_check?: {
                kind: "none" | "geofence_overlap";
                overlaps: Array<{ name: string }>;
              };
            })
          : null;
      if (submitted) {
        for (const file of hinhAnhMoi) {
          const form = new FormData();
          form.append("file", file);
          const imageResponse = await apiText(
            `/owner/submissions/${submitted.submission_id}/images`,
            {
              method: "POST",
              body: form,
            },
          );
          if (!imageResponse.ok) {
            setLoi(
              await apiErrorMessage(
                imageResponse,
                "Gửi quán thành công nhưng tải ảnh thất bại",
              ),
            );
            break;
          }
        }
      }
      const overlapWarning =
        submitted?.collision_check?.kind === "geofence_overlap"
          ? " Submission có cảnh báo phạm vi geofence chồng lấn; Admin sẽ xem lại."
          : "";
      setThongBaoGui(
        `Đã gửi thông tin quán thành công! Quán đang chờ Admin phê duyệt.${overlapWarning}`,
      );
      setTenQuan("");
      setMoTa("");
      setDiaChi("");
      setViDo("");
      setKinhDo("");
      setTenThucDon("Menu chính");
      setMoTaThucDon("");
      setMonTrongThucDon([{ name: "", description: "", price: "" }]);
      setPoiDangSua("");
      setGoiYAI("");
      setKinhDo("");
      setDanhMuc("other");
      setNgonNguNguon("vi");
      setBanKinh("30");
      setHinhAnhMoi([]);
      setTenThucDon("Menu chính");
      await taiLichSu();
    } catch {
      setLoi(
        "Không kết nối được máy chủ để gửi quán. Vui lòng kiểm tra kết nối và thử lại.",
      );
    } finally {
      setDangGui(false);
    }
  };

  if (user === null && checkingSession) {
    return (
      <div className="notice notice--info">Đang khôi phục phiên chủ quán…</div>
    );
  }

  if (user === null) {
    return (
      <div className="login-card-wrapper login-card-wrapper--owner">
        <div className="card login-card owner-login-card">
          <div className="login-card__header">
            <div className="login-card__icon-wrap login-card__icon-wrap--owner">
              <svg
                className="login-card__icon"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="1.75"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  d="M3 21h18M3 7v1a3 3 0 006 0V7m0 1a3 3 0 006 0V7m0 1a3 3 0 006 0V7M3 7l2-4h14l2 4M5 21V10.85M19 21V10.85M9 21v-4a2 2 0 012-2h2a2 2 0 012 2v4"
                />
              </svg>
            </div>
            <span className="owner-login-card__eyebrow">
              CỔNG DÀNH CHO CHỦ QUÁN
            </span>
            <h2 className="card__title">
              {authMode === "login"
                ? "Chào mừng trở lại!"
                : "Cùng kể chuyện quán bạn"}
            </h2>
            <p className="card__subtitle">
              {authMode === "login"
                ? "Đăng nhập để quản lý thông tin và chia sẻ món ngon của quán."
                : "Tạo tài khoản chủ quán để gửi địa điểm của bạn đến cộng đồng."}
            </p>
          </div>

          <form
            className="owner-login-card__form"
            onSubmit={(event) => {
              event.preventDefault();
              if (authMode === "login") void dangNhap();
              else void dangKy();
            }}
          >
            <div className="field">
              <label className="field__label" htmlFor="owner-username">
                Tên đăng nhập
              </label>
              <input
                id="owner-username"
                className="input"
                placeholder="Nhập tên đăng nhập"
                autoComplete="username"
                required
                value={ten}
                onChange={(e) => setTen(e.target.value)}
              />
            </div>

            <div className="field">
              <label className="field__label" htmlFor="owner-password">
                Mật khẩu
              </label>
              <input
                id="owner-password"
                className="input"
                placeholder="Nhập mật khẩu"
                type="password"
                autoComplete={
                  authMode === "login" ? "current-password" : "new-password"
                }
                required
                value={matKhau}
                onChange={(e) => setMatKhau(e.target.value)}
              />
            </div>

            {authMode === "register" && (
              <div className="field">
                <label className="field__label" htmlFor="owner-cccd">
                  Số Căn cước công dân (CCCD)
                </label>
                <input
                  id="owner-cccd"
                  className="input"
                  placeholder="Nhập số CCCD"
                  autoComplete="off"
                  required
                  value={cccd}
                  onChange={(e) => setCccd(e.target.value)}
                />
                <span className="field__helper">
                  Thông tin CCCD được mã hóa và chỉ dùng để xác minh chủ quán.
                </span>
              </div>
            )}

            <button
              className="btn btn--primary btn--block btn--lg owner-login-card__submit"
              type="submit"
            >
              {authMode === "login" ? "Đăng nhập" : "Tạo tài khoản chủ quán"}
            </button>
          </form>

          {loi !== "" && (
            <div className="notice notice--error mt" role="alert">
              {loi}
            </div>
          )}
          <div className="owner-login-card__switch">
            <span>
              {authMode === "login" ? "Chưa có tài khoản?" : "Đã có tài khoản?"}
            </span>
            <button
              type="button"
              onClick={() => {
                setLoi("");
                setAuthMode(authMode === "login" ? "register" : "login");
              }}
            >
              {authMode === "login" ? "Đăng ký chủ quán" : "Đăng nhập"}
            </button>
          </div>
        </div>
      </div>
    );
  }

  const laDaDuyet = trangThai === "approved" || trangThai === "admin";
  const tenTrangThai =
    {
      approved: "Đã được duyệt",
      pending: "Đang chờ duyệt",
      rejected: "Đã bị từ chối",
      admin: "Tài khoản nội bộ",
      unavailable: "Chưa xác minh",
    }[trangThai] ?? "Chưa xác định";
  const navItems: PortalDashboardItem[] = [
    {
      key: "submission",
      label: "Gửi quán mới",
      icon: (
        <svg
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="1.7"
        >
          <path d="M3 21h18M3 7l2-4h14l2 4M4 7v1a3 3 0 0 0 6 0V7m0 1a3 3 0 0 0 6 0V7m0 1a3 3 0 0 0 6 0V7M5 11v10m14-10v10M9 21v-4a2 2 0 0 1 2-2h2a2 2 0 0 1 2 2v4" />
        </svg>
      ),
    },
    {
      key: "history",
      label: "Trạng thái gửi duyệt",
      badge: lichSu.filter((submission) => submission.status === "pending")
        .length,
      icon: (
        <svg
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="1.7"
        >
          <path d="M3 12a9 9 0 1 0 3-6.7L3 8" />
          <path d="M3 3v5h5m4-1v5l3 2" />
        </svg>
      ),
    },
    {
      key: "places",
      label: "Địa điểm của tôi",
      badge: poisCuaToi.length,
      icon: (
        <svg
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="1.7"
        >
          <path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0Z" />
          <circle cx="12" cy="10" r="3" />
        </svg>
      ),
    },
    {
      key: "qr",
      label: "Mã QR",
      icon: (
        <svg
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="1.7"
        >
          <rect x="3" y="3" width="7" height="7" rx="1" />
          <rect x="14" y="3" width="7" height="7" rx="1" />
          <rect x="3" y="14" width="7" height="7" rx="1" />
          <path d="M14 14h3v3h-3zm5 0h2m-7 5h3m2-2v4" />
        </svg>
      ),
    },
    {
      key: "menu",
      label: "Thực đơn",
      icon: (
        <svg
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="1.7"
        >
          <path d="M4 3v7a4 4 0 0 0 8 0V3M8 3v18m8-18v18m0-18c3 2 4 5 4 9h-4" />
        </svg>
      ),
    },
    {
      key: "notifications",
      label: "Thông báo",
      badge: thongBao.filter((item) => !item.read).length,
      icon: (
        <svg
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="1.7"
        >
          <path d="M18 8a6 6 0 0 0-12 0c0 7-3 7-3 9h18c0-2-3-2-3-9m-8 13h4" />
        </svg>
      ),
    },
  ];

  return (
    <PortalDashboard
      role="owner"
      username={user}
      title={
        {
          submission: "Gửi quán mới",
          history: "Trạng thái gửi duyệt",
          places: "Địa điểm của tôi",
          qr: "Mã QR địa điểm",
          menu: "Quản lý thực đơn",
          notifications: "Thông báo",
        }[dashboardTab]
      }
      description={
        dashboardTab === "submission"
          ? "Chia sẻ địa điểm ẩm thực của quán với cộng đồng Quận 4."
          : dashboardTab === "history"
            ? "Theo dõi kết quả kiểm duyệt các nội dung bạn đã gửi."
            : dashboardTab === "places"
              ? "Xem các địa điểm thuộc quyền quản lý và gửi nội dung cập nhật."
              : dashboardTab === "qr"
                ? "Tạo mã QR dẫn đến trang khám phá của các địa điểm đã được duyệt."
                : dashboardTab === "menu"
                  ? "Thêm, chỉnh sửa món ăn và cập nhật giá trên thực đơn của quán."
                  : "Cập nhật tình trạng duyệt và thông tin dành cho quán của bạn."
      }
      activeItem={dashboardTab}
      items={navItems}
      onNavigate={(key) => {
        if (
          key === "submission" ||
          key === "history" ||
          key === "places" ||
          key === "qr" ||
          key === "menu" ||
          key === "notifications"
        ) {
          setDashboardTab(key);
          navigateToPath(getPortalPath("owner", key));
        }
      }}
      onLogout={() => void dangXuat()}
    >
      <section
        className="dashboard-metrics dashboard-metrics--owner"
        aria-label="Tổng quan tài khoản"
      >
        <div className="dashboard-metric">
          <span
            className="dashboard-metric__icon dashboard-metric__icon--blue"
            aria-hidden="true"
          >
            ✓
          </span>
          <span className="dashboard-metric__label">Trạng thái tài khoản</span>
          <strong className="dashboard-metric__status">{tenTrangThai}</strong>
          <span className="dashboard-metric__hint">
            Xác minh tài khoản chủ quán
          </span>
        </div>
        <div className="dashboard-metric">
          <span
            className="dashboard-metric__icon dashboard-metric__icon--violet"
            aria-hidden="true"
          >
            ♡
          </span>
          <span className="dashboard-metric__label">Thông báo</span>
          <strong aria-live="polite">
            {thongBao.filter((item) => !item.read).length}
          </strong>
          <span className="dashboard-metric__hint">thông báo chưa đọc</span>
        </div>
      </section>

      {loi !== "" && (
        <div className="notice notice--error dashboard-notice" role="alert">
          {loi}
        </div>
      )}
      {loiThongBao !== "" && (
        <div className="notice notice--error dashboard-notice" role="alert">
          {loiThongBao}
        </div>
      )}
      {trangThai === "rejected" && (
        <div className="notice notice--warn dashboard-notice" role="status">
          Đăng ký Chủ quán bị từ chối{adminNote ? `: ${adminNote}` : "."}
        </div>
      )}

      {dashboardTab === "submission" && (
        <>
          {!laDaDuyet && (
            <div
              className={`notice ${trangThai === "unavailable" ? "notice--error" : "notice--warn"} dashboard-notice`}
            >
              {trangThai === "unavailable"
                ? "Không xác minh được trạng thái tài khoản. Vui lòng kiểm tra kết nối và đăng nhập lại."
                : "Tài khoản chưa được duyệt. Kết quả xử lý sẽ tự cập nhật tại đây."}
            </div>
          )}

          <div className="card dashboard-content-card">
            <div className="section-header">
              <div>
                <h2 className="card__title">Thông tin quán</h2>
                <p className="card__subtitle">
                  Điền thông tin quán và món ngon đặc sắc để du khách ghé thăm.
                </p>
              </div>
            </div>

            <div className="field">
              <label className="field__label" htmlFor="owner-submission-poi">
                Loại nội dung gửi
              </label>
              <select
                id="owner-submission-poi"
                className="input"
                value={poiDangSua}
                disabled={!laDaDuyet}
                onChange={(event) => {
                  const poiId = event.target.value;
                  setPoiDangSua(poiId);
                  const poi = poisCuaToi.find((item) => item.id === poiId);
                  setTenQuan(poi?.name ?? "");
                  setMoTa(poi?.description ?? "");
                  setDiaChi(poi?.address_line ?? "");
                  setViDo(poi ? String(poi.lat) : "");
                  setKinhDo(poi ? String(poi.lng) : "");
                  setDanhMuc(poi?.category ?? "other");
                  setNgonNguNguon(poi?.source_language ?? "vi");
                  setBanKinh(poi ? String(poi.trigger_radius) : "30");
                  setHinhAnhMoi([]);
                }}
              >
                <option value="">Đề xuất quán mới</option>
                {poisCuaToi.map((poi) => (
                  <option value={poi.id} key={poi.id}>
                    Cập nhật: {poi.name}
                  </option>
                ))}
              </select>
            </div>

            <div className="field">
              <label className="field__label">
                Tên quán ăn / Thương hiệu *
              </label>
              <input
                className="input"
                placeholder="Tên quán"
                value={tenQuan}
                disabled={!laDaDuyet}
                onChange={(e) => setTenQuan(e.target.value)}
              />
            </div>

            <div className="field">
              <label className="field__label">
                Mô tả món ăn & Câu chuyện ẩm thực
              </label>
              <textarea
                className="input textarea"
                rows={4}
                placeholder="Mô tả"
                value={moTa}
                disabled={!laDaDuyet}
                onChange={(e) => setMoTa(e.target.value)}
              />
            </div>

            <div className="field">
              <label className="field__label" htmlFor="owner-poi-address">
                Địa chỉ quán *
              </label>
              <input
                id="owner-poi-address"
                className="input"
                placeholder="Số nhà, đường, phường..."
                value={diaChi}
                disabled={!laDaDuyet}
                onChange={(event) => setDiaChi(event.target.value)}
              />
            </div>

            <div className="form-grid-2">
              <div className="field">
                <label className="field__label" htmlFor="owner-poi-category">
                  Danh mục POI *
                </label>
                <select
                  id="owner-poi-category"
                  className="input"
                  value={danhMuc}
                  disabled={!laDaDuyet}
                  onChange={(event) => setDanhMuc(event.target.value)}
                >
                  <option value="restaurant">Nhà hàng</option>
                  <option value="cafe">Cà phê</option>
                  <option value="street_food">Ẩm thực đường phố</option>
                  <option value="bakery">Tiệm bánh</option>
                  <option value="dessert">Tráng miệng</option>
                  <option value="seafood">Hải sản</option>
                  <option value="bar">Quán bar</option>
                  <option value="other">Khác</option>
                </select>
              </div>
              <div className="field">
                <label
                  className="field__label"
                  htmlFor="owner-poi-source-language"
                >
                  Ngôn ngữ nguồn *
                </label>
                <select
                  id="owner-poi-source-language"
                  className="input"
                  value={ngonNguNguon}
                  disabled={!laDaDuyet}
                  onChange={(event) => setNgonNguNguon(event.target.value)}
                >
                  <option value="vi">Tiếng Việt</option>
                  <option value="en">English</option>
                  <option value="zh">中文</option>
                  <option value="ja">日本語</option>
                  <option value="ko">한국어</option>
                </select>
              </div>
            </div>

            <div className="field">
              <label
                className="field__label"
                htmlFor="owner-poi-trigger-radius"
              >
                Bán kính kích hoạt (m) *
              </label>
              <input
                id="owner-poi-trigger-radius"
                className="input"
                type="number"
                min="5"
                max="200"
                step="1"
                value={banKinh}
                disabled={!laDaDuyet}
                onChange={(event) => setBanKinh(event.target.value)}
              />
            </div>

            <div className="field">
              <label className="field__label" htmlFor="owner-poi-images">
                Hình ảnh POI (tối đa 8 ảnh, 5 MB/ảnh)
              </label>
              <input
                id="owner-poi-images"
                className="input"
                type="file"
                accept="image/jpeg,image/png,image/webp"
                multiple
                disabled={!laDaDuyet}
                onChange={(event) =>
                  setHinhAnhMoi(
                    Array.from(event.target.files ?? []).slice(0, 8),
                  )
                }
              />
            </div>

            <div className="form-grid-2">
              <div className="field">
                <label className="field__label" htmlFor="owner-poi-latitude">
                  Vĩ độ (Latitude) *
                </label>
                <input
                  id="owner-poi-latitude"
                  className="input"
                  type="number"
                  step="any"
                  placeholder="10.7569"
                  value={viDo}
                  disabled={!laDaDuyet}
                  onChange={(event) => setViDo(event.target.value)}
                />
              </div>
              <div className="field">
                <label className="field__label" htmlFor="owner-poi-longitude">
                  Kinh độ (Longitude) *
                </label>
                <input
                  id="owner-poi-longitude"
                  className="input"
                  type="number"
                  step="any"
                  placeholder="106.7641"
                  value={kinhDo}
                  disabled={!laDaDuyet}
                  onChange={(event) => setKinhDo(event.target.value)}
                />
              </div>
            </div>

            <div className="button-group mt">
              <button
                className="btn btn--primary"
                type="button"
                disabled={!laDaDuyet || dangXuLyAI || dangGui}
                onClick={() => void guiQuan()}
              >
                Gửi
              </button>
              <button
                className="btn btn--accent"
                type="button"
                disabled={!laDaDuyet || dangXuLyAI}
                onClick={() => void aiAdvisor()}
              >
                {dangXuLyAI ? "Đang tạo gợi ý…" : "AI gợi ý mô tả"}
              </button>
            </div>

            {goiYAI !== "" && (
              <div className="notice notice--info mt" role="status">
                {goiYAI}
              </div>
            )}
            {thongBaoGui !== "" && (
              <div className="notice notice--ok mt">{thongBaoGui}</div>
            )}
          </div>
        </>
      )}

      {dashboardTab === "history" && (
        <div className="card dashboard-content-card">
          <div className="section-header">
            <div>
              <h2 className="card__title">Nội dung đã gửi</h2>
              <p className="card__subtitle">
                Theo dõi tiến trình xét duyệt từng đề xuất của bạn.
              </p>
            </div>
            <div className="row">
              <span className="badge badge--neutral">{lichSu.length} mục</span>
              <button
                type="button"
                className="btn btn--secondary btn--sm"
                disabled={!laDaDuyet || trangThaiLichSu === "loading"}
                onClick={() => void taiLichSu()}
              >
                Tải lại lịch sử
              </button>
            </div>
          </div>

          {!laDaDuyet && (
            <p role="status">
              Tài khoản cần được duyệt trước khi gửi nội dung quán.
            </p>
          )}
          {laDaDuyet && trangThaiLichSu === "loading" && (
            <p role="status">Đang tải lịch sử gửi duyệt…</p>
          )}
          {laDaDuyet && trangThaiLichSu === "error" && (
            <p role="alert" className="notice notice--error">
              Không tải được lịch sử gửi duyệt. Vui lòng bấm Tải lại lịch sử.
            </p>
          )}
          {laDaDuyet && trangThaiLichSu === "ready" && lichSu.length === 0 ? (
            <div className="empty-state">
              <p className="muted">Bạn chưa gửi nội dung nào để kiểm duyệt.</p>
            </div>
          ) : laDaDuyet && lichSu.length > 0 ? (
            <div className="table-responsive mt">
              <table className="table">
                <thead>
                  <tr>
                    <th>Nội dung</th>
                    <th>Loại</th>
                    <th>Ngày gửi</th>
                    <th>Trạng thái</th>
                    <th>Phản hồi Admin</th>
                  </tr>
                </thead>
                <tbody>
                  {lichSu.map((submission) => {
                    const data = submission.data;
                    const tenNoiDung =
                      typeof data.name === "string"
                        ? data.name
                        : typeof data.title === "string"
                          ? data.title
                          : (submission.poi_id ?? "Nội dung quán");
                    const trangThaiLabel =
                      {
                        pending: "Đang chờ duyệt",
                        approved: "Đã được duyệt",
                        rejected: "Cần chỉnh sửa",
                        withdrawn: "Đã rút",
                      }[submission.status] ?? submission.status;
                    return (
                      <tr key={submission.id}>
                        <td>
                          <strong>{tenNoiDung}</strong>
                        </td>
                        <td>
                          {(submission.submission_type ??
                            (submission.poi_id ? "update" : "create")) ===
                          "update"
                            ? "Cập nhật quán"
                            : "Quán mới"}
                        </td>
                        <td>
                          {submission.created_at
                            ? new Date(
                                submission.created_at,
                              ).toLocaleDateString("vi-VN")
                            : "—"}
                        </td>
                        <td>
                          <span
                            className={`badge badge--${submission.status === "approved" ? "ok" : submission.status === "rejected" ? "error" : "warn"}`}
                          >
                            {trangThaiLabel}
                          </span>
                        </td>
                        <td>{submission.admin_note || "—"}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          ) : null}
        </div>
      )}

      {dashboardTab === "places" && (
        <div className="owner-poi-grid">
          {poisCuaToi.length === 0 ? (
            <div className="card dashboard-content-card">
              <div className="empty-state">
                <p className="muted">
                  Tài khoản của bạn chưa có địa điểm được quản lý.
                </p>
              </div>
            </div>
          ) : (
            poisCuaToi.map((poi) => (
              <article key={poi.id} className="card owner-poi-card">
                <div className="owner-poi-card__heading">
                  <div>
                    <h2>{poi.name}</h2>
                    <p>
                      {poi.address_line || "Chưa có địa chỉ"} ·{" "}
                      {poi.lat.toFixed(5)}, {poi.lng.toFixed(5)} · Bán kính{" "}
                      {poi.trigger_radius}m
                    </p>
                  </div>
                  <span
                    className={`badge badge--${poi.publication_status === "published" && poi.is_active ? "ok" : "warn"}`}
                  >
                    {poi.publication_status === "published" && poi.is_active
                      ? "Đang công khai"
                      : poi.publication_status === "unpublished"
                        ? "Đã duyệt · chưa công khai"
                        : poi.publication_status === "pending_review"
                          ? "Đã duyệt · chờ xuất bản"
                          : "Đang xử lý"}
                  </span>
                </div>
                {poi.publication_status === "unpublished" && (
                  <p className="notice notice--info">
                    Nội dung đã duyệt. Admin cần chuẩn bị English và audio, sau
                    đó bấm Công khai để khách thấy POI. Xem Thông báo để biết
                    lần thay đổi gần nhất.
                  </p>
                )}
                <p className="owner-poi-card__description">
                  {poi.description || "Chưa có mô tả."}
                </p>
                {poi.audio_url && layUrlAnh(poi.audio_url) && (
                  <audio
                    {...{ src: layUrlAnh(poi.audio_url) }}
                    className="owner-poi-card__audio"
                    controls
                    preload="none"
                  >
                    Trình duyệt không hỗ trợ phát audio.
                  </audio>
                )}
                <button
                  className="btn btn--secondary btn--sm"
                  type="button"
                  onClick={() => {
                    setPoiDangSua(poi.id);
                    setTenQuan(poi.name);
                    setMoTa(poi.description);
                    setDiaChi(poi.address_line);
                    setViDo(String(poi.lat));
                    setKinhDo(String(poi.lng));
                    setDashboardTab("submission");
                  }}
                >
                  Gửi cập nhật
                </button>
              </article>
            ))
          )}
        </div>
      )}

      {dashboardTab === "menu" && (
        <OwnerMenuManagement
          pois={poisCuaToi.map(({ id, name }) => ({ id, name }))}
        />
      )}

      {dashboardTab === "qr" && <OwnerPoiQrCodes pois={poisCuaToi} />}

      {dashboardTab === "notifications" && (
        <div className="card dashboard-content-card">
          <div className="section-header">
            <div>
              <h2 className="card__title">Thông báo</h2>
              <p className="card__subtitle">
                Các cập nhật từ đội ngũ vận hành.
              </p>
            </div>
            <span className="badge badge--neutral">{thongBao.length} thư</span>
          </div>

          {thongBao.length === 0 ? (
            <div className="empty-state">
              <p className="muted">Bạn chưa có thông báo nào mới.</p>
            </div>
          ) : (
            <ul className="notification-list">
              {thongBao.map((t) => (
                <li
                  key={t.id}
                  className={`notification-item${!t.read ? " notification-item--unread" : ""}`}
                >
                  <div className="spread">
                    <div className="notification-item__content">
                      {!t.read && (
                        <span className="badge badge--error mr">Mới</span>
                      )}
                      <span>{t.message}</span>
                    </div>
                    {!t.read && (
                      <button
                        className="btn btn--secondary btn--sm"
                        type="button"
                        onClick={() => void danhDauDaDoc(t.id)}
                      >
                        Đánh dấu đã đọc
                      </button>
                    )}
                  </div>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </PortalDashboard>
  );
}
