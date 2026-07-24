# Bible — Nguyên tắc phát hiện tín hiệu

> Mọi ngưỡng, mọi detector, mọi quyết định "kêu chuông hay im" đều PHẢI trỏ ngược
> về file này. Ngưỡng trong `config.py` là *phái sinh*; đây là *gốc*. Muốn đổi ngưỡng
> → sửa nguyên tắc ở đây trước, rồi mới sửa code. Không tune theo cảm giác.

## 0. Tiên đề nền — "đây là STOCK, không phải coin"

Mọi thứ bên dưới đứng trên các ràng buộc thị trường VN, không lách được:

| Tiên đề | Hệ quả lên detection |
|---|---|
| **T+2**: mua T, cổ về & bán được sớm nhất T+2 | Đơn vị hành động nhỏ nhất ≈ 2 phiên. **Không lướt trong ngày.** Tín hiệu intraday đứng một mình = vô dụng để hành động. |
| **Nghỉ cuối tuần** (5 phiên/tuần) | T+2 có thể kéo tới 4 ngày lịch; ôm qua cuối tuần = gánh rủi ro tin tức. Quyết định theo *phiên*, không realtime 24/7. |
| Tín hiệu dòng tiền **phân rã nhanh** | Dấu chân smart money tuần này → tháng sau hết nghĩa. |
| Biên độ **±7% (HOSE)** | "Sàn" ≈ −6.5%..−7%; nền cho ngưỡng force-sell. |
| **Không bán khống** | "Tín hiệu thoát" = ra hàng / tránh mua, KHÔNG phải mở short. |
| Phí + thuế bán ~0.1%+ | Sóng quá nhỏ không bõ; cần sàn "đáng lướt". |

**Kết luận tiên đề:** thứ bot detect được hợp **LƯỚT SÓNG**, không hợp **TÍCH SẢN**.

## 1. Châm ngôn đầu tư (creed)

> **Lướt sóng theo dấu chân smart money.**
> Bắt lúc con sóng *hình thành* (tiền lớn — khối ngoại + quỹ mở — bắt đầu vào) →
> cưỡi qua **vài phiên đến vài tuần** → *thoát* khi dòng tiền đảo chiều.
> Tích lũy đa phiên chỉ là *bối cảnh/setup*, KHÔNG phải đích ôm dài hạn.

## 2. Khẩu vị rủi ro — bất đối xứng vào/thoát

Kẻ thù số một của lướt sóng dưới T+2 = **false breakout** (vào theo sóng giả, sóng
xịt, kẹt ≥2 phiên không thoát được).

| | Khẩu vị | Vì sao |
|---|---|---|
| **Điểm VÀO** | Thà **sót** còn hơn **báo sai** → ngưỡng chặt, cần xác nhận | Vào hụt chỉ mất cơ hội; vào sai = kẹt hàng T+2 |
| **Điểm THOÁT** | Thà **báo sớm** còn hơn **sót** → ngưỡng nhạy | Thoát trễ = ôm sóng tàn qua T+2, đau hơn thoát hụt |

→ **Tín hiệu THOÁT phải to tiếng NGANG tín hiệu VÀO** (xem gap §6).

## 3. Con cá săn = vòng đời con sóng

Không phải "gom rồi giữ", mà là 4 pha:

1. **Setup / bối cảnh** — tích lũy/phân phối đa phiên (`state`/regime).
2. **Điểm vào** — regime *chuyển sang* GOM + accel xác nhận sóng mạnh lên.
3. **Điểm thoát** — regime *chuyển sang* XẢ / dòng tiền đảo.
4. **Phanh khẩn cấp** — rủi ro hệ thống (force-sell/giải chấp diện rộng) → tránh kẹt sóng lớn.

## 4. Ưu tiên detector (phái sinh từ §0–3)

| Detector | Vai | Vì sao |
|---|---|---|
| `state`/regime | **Xương sống** | Đa phiên → sống với T+2, hợp lướt sóng |
| `accel` | Xác nhận sóng | Momentum nối tiếp = sóng thật |
| `spike` (10') | **Mầm / breadcrumb** | Intraday → chỉ đáng khi *nối tiếp* setup đa phiên; KHÔNG phải trigger độc lập |
| `forcesell`/breadth | Phanh khẩn | Bảo vệ khỏi kẹt sóng hệ thống |
| confluence (KN × quỹ) | Tăng độ tin | 2 nguồn smart-money đồng thuận |

## 5. Nguyên tắc đo lường

1. **Đo TIỀN (VND), không đo số cổ phiếu.** Giá cao/thấp không đổi ý nghĩa dòng tiền.
2. **"Đáng kể" phải TƯƠNG ĐỐI trên CẢ 2 trục**: áp đảo *nhịp* (share của window 10')
   **VÀ** đáng kể *so với chính mã* (share của GTGD ngày). Không dùng sàn tuyệt đối
   phẳng cho mọi mã — 4 tỷ với mã 30 tỷ/ngày khác hẳn 4 tỷ với mã 1.000 tỷ/ngày.
3. **Nền thanh khoản tối thiểu** (GTGD ngày ≥ ngưỡng) — mã quá mỏng thì bỏ.
4. **Persistence qua T+2**: tín hiệu chỉ lên tier "đáng tin / kêu chuông" khi đã *trụ
   qua ≥ chu kỳ hành động* (đa phiên). Bùng 1 nhịp rồi đảo = chưa đáng.

## 6. Tiering — khi nào kêu chuông (phái sinh từ §2)

- **VÀO — loud** chỉ khi: setup đa phiên (regime GOM) **+** xác nhận (accel/confluence). Chặt.
- **THOÁT — loud** khi: regime chớm chuyển XẢ / dòng tiền đảo. Nhạy, kêu sớm.
- **Silent**: mầm intraday (spike lẻ), tín hiệu chưa trụ qua phiên.
- **watchlist**: hạ ngưỡng cho mã bro đang ôm/ngó.

## 7. Khoảng cách (đã đóng — bám bible)

| # | Gap | Nguyên tắc | Đã đóng bằng |
|---|---|---|---|
| 1 | `spike` sàn tuyệt đối 3 tỷ, không xét % GTGD ngày (ca FRT) | §5.2 | `spike_share(min_day_share)` + `SPIKE_MIN_DAY_SHARE=5%`: net phải ≥ 5% GTGD ngày mã |
| 2 | Tín hiệu XẢ bị im lặng | §2, §6 | `detect_states`: `loud = regime=="XA" or confluence` — thoát kêu ngang vào |
| 3 | `spike` bị đối xử như trigger độc lập | §0, §4 | spike loud chỉ khi **nối tiếp setup đa phiên** (`_continues`) + hợp lưu quỹ; hoặc là thỏa thuận (share>80%, 1 sự kiện) |
| 4 | Chưa có "persistence qua T+2" tường minh | §5.4 | `trend_side` = chiều chuỗi phiên liên tiếp (streak≥2); spike phải cùng chiều mới lên loud. GOM-state loud vẫn dựa hợp lưu quỹ (bản thân đã bền); XẢ-state cố tình KHÔNG gate persistence (§2: thoát nhạy) |
| 5 | Entry/Exit dùng chung ngưỡng | §2 | `classify_regime(exit_th)` + `DAY_NET_TH_EXIT=10 tỷ` < `DAY_NET_TH=15 tỷ`: XẢ fire sớm hơn |

**Ngưỡng starter (tune khi có data):** `SPIKE_MIN_DAY_SHARE` 5%, `DAY_NET_TH_EXIT` 10 tỷ, `trend_side` streak ≥ 2 phiên. Đổi ngưỡng → sửa nguyên tắc §0–6 trước, rồi mới đụng `config.py`.
