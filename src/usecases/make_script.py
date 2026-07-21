"""Script TikTok tho (khong header Telegram) — chot 1 lan/ngay vao meta['script:<ngay>'].
Header + cap Telegram nam o noi gui (presenters.script_msg / TelegramBot.send_to)."""
from src.config import FLOOR_PCT, FORCESELL_MIN, MIN_DAY_VALUE, now_vn
from src.usecases.build_trend import trend_message
from src.usecases.funds import fund_summary_text

SCRIPT_SYSTEM = """Bạn là người viết kịch bản video TikTok ngắn (30-40 giây đọc thành tiếng) về chứng khoán Việt Nam.
Nhiệm vụ: từ dữ liệu giao dịch khối ngoại hôm nay, viết script cho 1 video.

Cấu trúc bắt buộc (plain text):
[HOOK] 1 câu mở đầu gây chú ý bằng con số ấn tượng nhất của phiên. Không chào hỏi.
[THÂN] 3-5 câu ngắn, kể ĐỦ 3 ý theo mạch: (1) chuỗi/xu hướng các phiên gần đây,
(2) sắc xanh/đỏ và % giá nổi bật của nhóm mã giao dịch lớn, (3) top gom/xả kèm số tỷ;
thêm điểm bất thường nếu có (đảo chiều, chuỗi phiên dài...). Nếu dữ liệu có dòng "Áp lực giải chấp"
thì ĐƯA LÊN [HOOK] hoặc câu đầu [THÂN] vì đó là điểm nóng nhất phiên — nêu như DẤU HIỆU
(vd "nhiều mã nằm sàn, dấu hiệu bán tháo/giải chấp diện rộng"), KHÔNG phán chắc, KHÔNG hù dọa kiểu "sắp sập".
[KẾT] 1 câu mời theo dõi kênh để cập nhật phiên sau.
Dòng cuối: 4-5 hashtag tiếng Việt.

Quy tắc: giọng nói chuyện tự nhiên, xưng "mình", câu ngắn dễ đọc thành tiếng, số liệu làm tròn
cho dễ nghe. KHÔNG khuyến nghị mua/bán. KHÔNG bịa gì ngoài dữ liệu được đưa. TRÁNH ngôn ngữ
cá cược/làm giàu ("đặt cửa", "x2 tài khoản", "ăn bằng lần") — dùng từ trung tính."""


def make_script(repo, flows, llm):
    key = f"script:{now_vn().date().isoformat()}"
    saved = repo.get_meta(key)
    if saved:
        return saved.split("🎬 Script TikTok hôm nay:\n\n")[-1]  # don gia tri cu con header (chuyen tiep, xoa duoc sau nay)
    data = trend_message("VNINDEX", repo, flows, movers=True)
    ts = repo.max_ts()
    if ts:  # % gia nhom GTGD lon — de script co the ke ve sac xanh/do (canh heatmap)
        heat = repo.heat(ts, 8)
        data += "\nGiá mã GTGD lớn hôm nay: " + ", ".join(f"{s} {p:+.1f}%" for s, p in heat)
        floors = repo.floor_stocks(ts, FLOOR_PCT, MIN_DAY_VALUE)  # giai chap dien rong -> diem nong phien
        if len(floors) >= FORCESELL_MIN:
            data += (f"\nÁp lực giải chấp: {len(floors)} mã thanh khoản lớn giảm sàn/gần sàn ("
                     + ", ".join(s for s, _ in floors[:6]) + ") — dấu hiệu bán tháo/giải chấp diện rộng.")
    data += fund_summary_text(repo)  # hop luu quy mo — canh scene "funds" cua video
    text = llm.complete(SCRIPT_SYSTEM, f"Dữ liệu phiên hôm nay:\n\n{data}\n\nViết script.").strip()
    repo.set_meta(key, text)
    return text
