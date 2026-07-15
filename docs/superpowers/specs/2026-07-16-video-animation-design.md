# video.py — animated, data-rich slides (design)

Ngày: 2026-07-16
Bối cảnh: feedback sau bản đầu — "data visual ít quá, không có animation, keyframe
các thứ — cần sinh động hơn và bám sát theo script".

## Mục tiêu

Video TikTok 1080×1920 hàng ngày với animation thật (count-up, bar mọc, card trượt,
karaoke caption), nhiều data visual hơn (heatmap, movers có giá/%), visual đồng bộ
với lời đọc. Không thêm dependency mới (PIL + ffmpeg đã có).

## Pipeline

Thay "3 PNG tĩnh × 3 segment + concat" bằng:

1. `make_script(db)` → tách `[HOOK]/[THÂN]/[KẾT]` (giữ nguyên).
2. TTS từng đoạn (Gemini Leda, giữ nguyên) → đọc duration mỗi wav bằng module `wave`.
3. Nối 3 wav thành 1 track (cùng format 24kHz/mono/16-bit, ghép frames bằng `wave`).
4. Dựng timeline 5 cảnh theo duration thật → render **từng frame 30fps bằng PIL**,
   pipe raw RGB24 vào **một** lệnh ffmpeg (`-f rawvideo -s 1080x1920 -r 30 -i - -i audio.wav`)
   → `video_out/daily.mp4`.

## Timeline & cảnh (d₀,d₁,d₂ = duration 3 đoạn TTS)

| Cảnh | Khoảng | Nội dung & animation |
|---|---|---|
| Hook | `[0, d₀)` | Tiêu đề + ngày trượt vào; dòng nhỏ VN-Index (điểm, ±, %); con số ròng **count-up 0.8–1.2s** ease-out cubic, xanh/đỏ theo dấu. Payoff trong 3s đầu (quy tắc 3 giây TikTok). |
| Chart | `[d₀, d₀+0.4·d₁)` | Bar 10 phiên **mọc dần**, so le 0.06s/cột, cột hôm nay sáng hơn + viền. |
| Heatmap | `[d₀+0.4·d₁, d₀+0.7·d₁)` | Lưới ô kiểu Bản đồ thị trường: top ~20 mã theo `day_value` từ **snapshot mới nhất**, ô tô xanh/đỏ đậm nhạt theo `pct`, hiện lần lượt, label `MÃ %`. |
| Movers | `[d₀+0.7·d₁, d₀+d₁)` | Card GOM/XẢ trượt vào từng cái: mã, net tỷ, giá, %▲▼ (màu theo dấu). |
| Outro | `[d₀+d₁, hết)` | CTA pop-in (scale ease), disclaimer fade. |

- Chuyển cảnh: crossfade 0.35s, blend trong Python (ta kiểm soát mọi frame).
- Nền: gradient tối trôi chậm — vẽ ở 135×240 rồi upscale (rẻ, mượt).
- Mốc 0.4/0.7 của THÂN là hằng số module, chỉnh được khi xem bản đầu.

## Caption karaoke

- Không có word-timestamp từ Gemini TTS → chia lời thoại mỗi đoạn thành **cụm 4–6 từ**,
  phân bổ thời gian tỷ lệ theo số ký tự trên duration đoạn. Drift theo cụm gần như
  không nhận ra.
- Cụm đang đọc: to, sáng; cụm trước: mờ dần. 1–2 dòng.
- Vị trí: vùng an toàn TikTok — mép dưới block caption cách đáy ≥ 340px, text căn
  giữa với max width `W − 300` (chừa UI phải). (Nghiên cứu OpusClip 13.5M clips:
  78.6% dùng caption động; đặt giữa/1-3 trên để không bị UI che.)

## Data

- Có sẵn: `snapshots` (net, `price`, `pct`, `day_value` từng mã — đủ cho heatmap +
  movers), `fetch_foreign_daily("VNINDEX")` cho chart 10 phiên.
- Mới: `fetch_index()` trong video.py — GET
  `https://api-finfo.vndirect.com.vn/v4/vnmarket_prices?q=code:VNINDEX&size=1&sort=date:desc`
  → `close`, `change`, `pctChange` (đã verify hoạt động). Lỗi/timeout → **bỏ dòng
  VN-Index, video vẫn render** (try/except quanh call này).

## Error handling

Giữ hành vi hiện tại: TTS/ffmpeg lỗi thì exception nổi lên, `check=True`. Ngoại lệ
duy nhất được nuốt: `fetch_index()` (nói trên).

## Kiểm tra

- `python video.py --preview`: render vài PNG giữa mỗi cảnh với duration giả —
  **không cần API/TTS/ffmpeg**, xem visual trong vài giây.
- E2E: `python video.py` / `--send` như cũ.

## Hiệu năng

~30–60s video ≈ 900–1800 frames PIL thuần → mục tiêu render < 3 phút trên máy local.

## Ngoài phạm vi

- Font vẫn hardcode đường dẫn macOS (job chạy local; sửa khi deploy video lên server).
- Nội dung/độ dài script (`SCRIPT_SYSTEM`) giữ nguyên — follow-up riêng nếu muốn ép
  21–34s theo chuẩn completion-rate TikTok.
- Tổ chức code: tất cả trong `video.py` (~400 dòng), mỗi cảnh một hàm `scene_*(img, ctx, t)`
  với `t` chuẩn hoá 0→1, helpers `ease/lerp/crossfade` dùng chung.

## Reference format (research 2026-07-16)

- Thứ tự thông tin recap VN quen mắt: VN-Index → độ rộng → thanh khoản → khối ngoại
  → top mã (infographic Nhân Dân, VNFDATA "điểm nhấn").
- Heatmap = visual chuẩn của recap VN (Bản đồ thị trường Vietstock).
- Hook ≤ 3s: 63% video CTR cao nhất hook trong 3s; retention 3s > 65% → 4–7×
  impressions (TikTok for Business).
- Caption động vượt trội caption tĩnh (78.6% vs 1.6%, OpusClip).
