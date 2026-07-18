# Đặc tả Metric — Palantir trên nguồn Fmarket (Phân tích danh mục quỹ, bản build được)

## 0. Quan hệ với bản gốc

Bản gốc (`Metrics-Project-Palantir (1).md`) đặc tả model chạy trên pipeline nội bộ — **không dùng được** cho dự án cá nhân. Bản này là đặc tả thay thế, chạy hoàn toàn trên **nguồn công khai Fmarket** qua pipeline của bot (`src/infrastructure/fmarket_api.py` → `flows.db` → `python -m src.export` → CSV → Power BI Desktop).

Khác biệt gốc rễ so với bản cũ, quyết định metric nào sống: nguồn mới **không có giá trị VND** (không AUM quỹ, không giá trị từng khoản), **không có khối lượng**, chỉ có **tỷ trọng %**, **số quỹ nắm giữ**, và **hiệu suất NAV**. Đổi lại: mỗi quỹ chỉ công bố **top 10 khoản** — "không thấy ≠ không nắm" phải ghi vào mọi tooltip liên quan.

Mỗi metric mô tả bằng lời, bốn phần như bản gốc: trả lời gì / lấy từ đâu / tính thế nào / ràng buộc.

## 1. Nguồn dữ liệu và cấu trúc bảng

Bốn file CSV do `python -m src.export` sinh ra (UTF-8 BOM), refresh **thủ công 1 lần/tháng** sau khi bot chụp (từ ngày 15). Đường dẫn thư mục export khai báo dưới dạng **tham số** trong Power Query.

| Bảng | Mức chi tiết (mỗi dòng là) | Ứng với bản gốc |
|---|---|---|
| `fund_holdings` | tháng chụp × quỹ × mã | `fact_equity_report` (chỉ còn `pct`, mất value/volume/price) |
| `fund_assets` | tháng chụp × quỹ × loại tài sản | `fact_equity_asset` (chỉ còn %) |
| `fund_industries` | tháng chụp × quỹ × ngành | `fact_equity_industry` (chỉ còn %) |
| `fund_snapshot` | tháng chụp × quỹ | mới: owner, tháng báo cáo, NAV + hiệu suất 1m/3m/6m/12m/36m |

**Hai loại "tháng" — phải hiểu trước khi build.** `month` là **tháng chụp** (bot gọi API ngày 15+ hàng tháng) — key đồng nhất cho mọi bảng, dùng làm slicer chính. `fund_snapshot[report_month]` là **tháng báo cáo danh mục thật** của từng quỹ (thường trễ 1 tháng so với tháng chụp, và **có thể lệch nhau giữa các quỹ**). Mọi phép so sánh kỳ dùng `month`; `report_month` để hiển thị độ tươi dữ liệu (mục 6).

**Bảng chiều (tự sinh trong Power Query, không có file riêng):**
- `dim_month`: DISTINCT `month` từ `fund_snapshot` + cột `month_index` (xếp hạng tăng dần). So sánh "tháng trước" làm bằng `month_index - 1`, **không dùng hàm time-intelligence theo ngày** — dữ liệu chỉ có grain tháng, bảng lịch ngày là thừa.
- `dim_fund`: DISTINCT (`fund`, `owner`) từ `fund_snapshot`. `owner` (công ty quản lý) là slicer tương đương `Issuer` bản gốc.
- `dim_stock`: DISTINCT `symbol` từ `fund_holdings`. **Không** kéo `industry` vào đây — ngành ghi kèm từng dòng holdings vì mỗi quỹ có thể phân ngành khác nhau (bản gốc §8.6 đã kết luận đây là thông tin, không phải trùng lặp).

## 2. Quan hệ

Star schema, một-nhiều, lọc một chiều, khai báo tường minh — nguyên tắc y bản gốc:

`dim_month[month]` → 4 bảng fact; `dim_fund[fund]` → `fund_holdings`, `fund_assets`, `fund_industries`, `fund_snapshot`; `dim_stock[symbol]` → `fund_holdings`.

Hệ quả giữ nguyên từ bản gốc: bộ lọc không chảy ngược từ fact lên dim → **mọi phép đếm hoạt động phải đếm trên bảng fact**.

## 3. Nguyên tắc tính chung

1. **Không cộng cột %** — `pct` trong cả 3 bảng là tỷ trọng tính sẵn, chỉ hợp lệ ở đúng grain quỹ × tháng. Cảnh báo §5.6 bản gốc áp dụng nguyên văn, và ở đây **không có đường tính lại từ giá trị** (không có VND) — nên thay vì tính lại, quy tắc là: mọi mức gộp qua quỹ chỉ được dùng AVERAGE (ghi rõ "trung bình không trọng số — không có AUM để weight") hoặc không hiển thị.
2. **Chia an toàn** — mẫu số 0/rỗng → rỗng.
3. **So sánh kỳ chỉ có nghĩa ở ngữ cảnh đúng 1 tháng** — mọi metric `... LM/Diff` kiểm tra ngữ cảnh có đúng một `month`, sai thì trả rỗng (quy tắc 3 bản gốc, áp cho cả Diff lẫn %).

## 4. Nhóm metric: Đếm và đồng thuận (trọng tâm của bản này)

**Fund Count** — bao nhiêu quỹ trong bản chụp kỳ này? DISTINCTCOUNT `fund_snapshot[fund]`. Đếm trên fact, không đếm `dim_fund` (nguyên tắc bản gốc §4.1).

**Stock Count** — bao nhiêu mã xuất hiện trong top 10 của ít nhất một quỹ? DISTINCTCOUNT `fund_holdings[symbol]`. Tooltip: "trong top 10 công bố".

**Holders** — mã này được bao nhiêu quỹ nắm (trong top 10)? DISTINCTCOUNT `fund_holdings[fund]` trong ngữ cảnh mã + tháng. Đây là metric xương sống của bản này (bản gốc §7.2 lấy sẵn `no_holders` từ nguồn; ở đây tự đếm — kết quả tương đương, còn chủ động hơn).

**Holders LM** — như Holders nhưng dịch về `month_index - 1` qua `dim_month`. Ràng buộc: gỡ lọc tháng, **giữ lọc mã/quỹ/owner** (bản gốc §3.3); ngữ cảnh nhiều tháng → rỗng.

**Holders Diff** = Holders − Holders LM. Mã không còn trong kỳ hiện tại → rỗng (không hiện số âm giả — quy tắc 1 bản gốc §6.3). Cách đọc giữ nguyên tinh thần bản gốc §7.3: tín hiệu đồng thuận, không nhiễu giá.

**New Positions / Exited** — mã có Holders > 0 kỳ này và = 0 kỳ trước (và ngược lại). Lưu ý trung thực bắt buộc trong tooltip: vào/ra **top 10** chứ không chắc vào/ra danh mục — mã có thể chỉ rơi từ hạng 10 xuống 11.

## 5. Nhóm metric: Tỷ trọng và phân bổ

**% NAV (per quỹ × mã)** — `fund_holdings[pct]`, chỉ hiển thị ở grain quỹ × mã × tháng. Dòng tổng phụ: rỗng hoặc AVERAGE có chú thích, tuyệt đối không SUM.

**Avg Conviction %** — các quỹ đang nắm thì phân bổ trung bình bao nhiêu vào mã này? AVERAGE `fund_holdings[pct]` theo mã. Đây là proxy "độ tin" bổ sung cho Holders (nhiều quỹ nắm nhẹ ≠ ít quỹ nắm đậm).

**Stock/Cash Allocation %** — từ `fund_assets`, lọc `asset = "Cổ phiếu"` / `"Tiền và tương đương tiền"`. Per quỹ; gộp qua quỹ = AVERAGE không trọng số + chú thích. Cash allocation trung bình tăng qua các tháng = tín hiệu phòng thủ của cả nhóm quỹ — metric tổng hợp đáng đặt lên trang đầu.

**Industry Allocation %** — từ `fund_industries`, cùng quy tắc.

**Disclosed Coverage %** — quỹ công bố được bao nhiêu phần danh mục cổ phiếu? SUM(`fund_holdings[pct]`) của quỹ ÷ Stock Allocation % của quỹ đó, cùng tháng. Sống nguyên từ bản gốc §5.4 dưới dạng thuần %, không cần VND. Cách đọc giữ nguyên: tụt đột ngột = quỹ giảm minh bạch hoặc pipeline thiếu dữ liệu. Chia an toàn; > 100% một chút có thể xảy ra do làm tròn — clamp hiển thị tại 100%, nhưng > 110% thì là lỗi dữ liệu, phải điều tra.

## 6. Nhóm metric: Hiệu suất và metadata

**NAV, NAV 1m/3m/6m/12m/36m** — từ `fund_snapshot`, per quỹ. Nhóm này bản gốc không có — dùng cho trang "quỹ nào đang thắng": bảng xếp hạng quỹ theo `nav_12m`, slicer `owner`. Không AVERAGE hiệu suất qua quỹ khi so sánh — hiển thị dạng bảng xếp hạng.

**Latest Snapshot** — MAX `month`, định dạng tường minh (bản gốc §7.1: không phụ thuộc locale máy người xem).

**Report Freshness** — MIN/MAX `fund_snapshot[report_month]` trong tháng chụp mới nhất. Nếu MIN < MAX: có quỹ báo cáo trễ hơn các quỹ khác — hiển thị cảnh báo nhỏ thay vì để người xem tưởng mọi quỹ cùng kỳ. (Thay thế cặp Last Update/Latest Report của bản gốc, cùng mục đích: đo độ tươi thật.)

## 7. Những gì KHÔNG build được từ nguồn này (traceability về bản gốc)

| Metric bản gốc | Số phận | Lý do / thay thế |
|---|---|---|
| Total Market Value, Total Stock, Stock AUM, Undisclosed Value (VND) | ❌ | Không có AUM quỹ (`holdingVolume` của API chỉ là lượng nắm qua kênh Fmarket — đã kiểm chứng với DCDS, lệch ~10 lần) |
| Stock Volume + toàn nhóm volume (§6.2–6.4) | ❌ | Không có khối lượng. Ma trận "giá lên vs quỹ mua thật" chỉ còn proxy yếu: pct tăng khi giá giảm ≈ mua thêm — nếu dùng phải ghi rõ là suy đoán |
| Avg Buying Price, Price vs Avg (§7.4, §8.4) | ❌ | Không có; bản gốc cũng chưa chắc chắn cột này nghĩa là gì |
| Rank by AUM | ⚠️ | Thay bằng rank theo Holders (chính), tie-break bằng Avg Conviction % |
| % Net Asset (§5.6) | ⚠️ | Có sẵn dạng % tính sẵn, dùng đúng grain như mục 5; không bao giờ tính lại được từ giá trị |

Nâng cấp tương lai nếu cần value + volume + full danh mục: WiGroup/WiFeed (trả phí) — mọi metric ❌ ở trên sống lại, model không phải đập vì grain giữ nguyên.

## 8. Cần chốt trước khi build

1. **Độ phủ quỹ**: 34 quỹ cổ phiếu trên Fmarket ≠ toàn bộ quỹ ở VN (thiếu quỹ không phân phối qua Fmarket và quỹ ngoại như PYN Elite, VEIL). Chấp nhận phạm vi "quỹ mở nội trên Fmarket" hay bổ sung tay từ factsheet? Khuyến nghị: chấp nhận, ghi rõ phạm vi lên tiêu đề dashboard.
2. **Grain hiển thị thời gian**: slicer chính theo `month` (tháng chụp — khuyến nghị, đồng nhất) hay `report_month` (đúng kỳ báo cáo nhưng lệch nhau giữa quỹ)?
3. **Chuẩn hóa tên ngành**: `industry` do từng quỹ tự khai, có thể không đồng nhất ("Ngân hàng" vs "Tài chính"). Xem dữ liệu thật vài tháng rồi quyết: giữ nguyên hay thêm bảng map thủ công.

## 9. Thứ tự build

```
dim_month (+ month_index) ─ điều kiện tiên quyết cho mọi metric LM
  Fund Count · Stock Count · Holders ─┬─ Holders LM ── Holders Diff ── New/Exited
                                       └─ Avg Conviction %
  Stock/Cash/Industry Allocation % ── Disclosed Coverage %   (cần SUM pct + Stock Allocation)
  NAV series · Latest Snapshot · Report Freshness             (độc lập)
```

## 10. Kiểm thử sau khi build

**Ca 1 — slicer tháng:** đổi `month`, Fund Count/Stock Count/Holders phải đổi theo (đếm trên fact — nếu đứng yên là đếm nhầm trên dim). Thử thêm slicer `owner`: metric sai vẫn phản ứng với owner, chỉ slicer tháng mới lộ lỗi.

**Ca 2 — %: dòng tổng phụ** theo owner: % NAV không được vượt kiểu 60% = 5% × 12 — nếu thấy là đã SUM cột %.

**Ca 3 — so sánh kỳ ở mức gộp:** cột tổng nhiều tháng → Holders Diff phải **trống**, không phải ~0.

**Ca 4 — mã vào/ra:** chọn 1 mã bot báo "Mới vào top" trong ảnh `/fund` tháng đó → New Positions phải khớp với ảnh của bot (hai đường tính độc lập, cùng dữ liệu — lệch là một trong hai sai).

**Ca 5 — coverage sanity:** mọi quỹ × tháng có Disclosed Coverage % trong (0, 110%]; ngoài khoảng đó là lỗi dữ liệu nạp.
