---
name: daily-video
description: Render + QA + gửi video TikTok khối ngoại hàng ngày từ data thật. Dùng khi user nói "làm video hôm nay", "video phiên hôm nay", "render video", "daily video", hoặc muốn kiểm tra/sửa video daily. Chạy LOCAL (cần ffmpeg + font macOS) — data intraday kéo từ Railway vì iBoard chặn IP datacenter và collector không chạy local.
---

# Daily Video — TikTok khối ngoại

Pipeline: data (Railway volume) → script (Gemini) → TTS (Gemini Leda) → render PIL
30fps pipe vào ffmpeg → QA frame bằng mắt → gửi Telegram. Làm ĐÚNG THỨ TỰ, không bỏ
bước QA — video đăng public, một frame lỗi là lên sóng luôn.

## Contract cố định (không tự chế)

- Chạy từ repo root bằng `.venv/bin/python`. Cần: ffmpeg, `.env` có `GEMINI_API_KEY`,
  railway CLI đã login + link project `meticulous-happiness`.
- Output: `video_out/daily.mp4` — 1080×1920, 30fps, audio AAC. Mỗi render tự lưu thêm
  bản `daily-YYYYMMDD-HHMM.mp4` (daily.mp4 bị ghi đè) và TỰ GỬI Telegram — khi đang
  QA/debug phải chạy với `--no-send`.
- Cảnh bám theo script (plan_scenes): câu nhắc tên mã → movers, %/sắc xanh đỏ →
  heatmap, chuỗi phiên → chart; script không nhắc thì cảnh đó không chiếu. Số đếm ở
  hook = số đầu tiên script đọc (hook_number).
- **Thời lượng chuẩn 21–34s** (completion-rate TikTok). >40s = script quá dài → báo
  user trước khi gửi, đừng tự gửi.
- **Palette ĐÓNG** — mọi màu trong `video.py` phải thuộc list này, thêm màu = sửa
  list có chủ đích: `BG(15,17,21)` `BG2(26,31,46)` `FG(240,240,245)`
  `GREEN(34,197,94)` `RED(239,68,68)` `DIM(140,145,160)` `HEAT_NEUTRAL(44,49,60)`
  card `(28,32,42)`.
- Caption karaoke nằm trong vùng an toàn TikTok: đáy block cách mép dưới ≥340px
  (`CAPTION_BOTTOM = H-360`), bề ngang ≤ `W-300`, căn giữa.
- **Dấu (±) không bao giờ chỉ mã hóa bằng màu** (cặp xanh-đỏ mù màu deutan ΔE 7.4):
  luôn kèm ▲/▼, MUA/BÁN RÒNG, GOM/XẢ, hoặc vị trí trên/dưới baseline.

## Workflow

1. **Sync data** — DB local luôn stale (collector sống trên Railway):
   ```bash
   railway volume files -v "$(railway volume list 2>/dev/null | grep '^Volume:' | head -1 | awk '{print $2}')" \
     download flows.db video_out/flows-railway.db --overwrite
   ```
   Kiểm tra tươi: `sqlite3 video_out/flows-railway.db "SELECT MAX(ts) FROM snapshots"`
   phải là hôm nay, sau 15:00 nếu render bản EOD.
2. **Render**: `DB_PATH=video_out/flows-railway.db .venv/bin/python video.py --no-send`
   (~1-2 phút: gọi Gemini script + TTS từng cảnh trả phí — đừng render lặp vô ích;
   TTS hết quota ngày sẽ tự fallback model, quá nữa thì báo user chờ).
3. **QA bắt buộc — nhìn hình thật, không tin code** (rule mượn từ noddle, từng cứu
   7/21 hình bên đó): `.venv/bin/python video.py --frames` rồi **Read TỪNG PNG**
   `video_out/frame_*.png` và soát:
   - Mọi frame đọc được đầy đủ nội dung — frame `_dau` mỗi cảnh là chỗ lộ lỗi:
     caption chưa hiện, count-up đang số lửng, bar chưa mọc mà label đã hiện.
   - Không chữ đè chữ / đè cột; heatmap 4×5 không tràn lề; card movers không chạm
     vùng caption.
   - ▲▼ / chữ chiều hiện cạnh mọi con số màu (không màu-trần).
   - `ffprobe -v error -show_entries format=duration -of csv=p=0 video_out/daily.mp4`
     trong khoảng 21–40s.
4. Lỗi → sửa `video.py` → chạy `--selftest` → render lại → QA lại đến sạch.
5. **Gửi**: `--send` gửi `daily.mp4` hiện có vào chat đầu tiên trong config, KHÔNG
   render lại. Nếu user chưa duyệt video trong session này thì hỏi trước khi gửi.

## Lỗi đã gặp (đừng lặp lại)

- iBoard 403 với IP datacenter → data intraday CHỈ lấy được từ Railway DB (hoặc IP VN).
- VNDirect daily trả CẢ ngày hôm nay → logic "phiên trước" phải lọc `tradingDate < today`.
- `changePc` của VPS datafeed không có dấu; field VPS là string.
- Font hardcode đường dẫn macOS — skill này chỉ chạy trên Mac, chưa deploy video lên server (quyết định có chủ đích, giữ human-in-the-loop).
