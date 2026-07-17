"""/brief MÃ — bản tin tổng hợp 1 mã: dòng tiền khối ngoại + cơ bản + tin tức
(brief.py:42-69,113-123,174-178). INFORMATION ONLY — không khuyến nghị mua/bán."""
from src.adapters import presenters
from src.infrastructure import news_api, vndirect_api

SYSTEM = """Bạn là trợ lý dữ liệu tài chính cho nhà đầu tư cá nhân Việt Nam.
Nhiệm vụ: tổng hợp dữ liệu được cung cấp thành bản tin ngắn về một cổ phiếu.

Quy tắc nội dung:
- CHỈ tổng hợp và diễn giải dữ liệu được đưa. Không bịa số liệu.
- TUYỆT ĐỐI không khuyến nghị mua/bán/nắm giữ, không dự đoán giá mục tiêu.
- Nếu dữ liệu mâu thuẫn (vd: KN bán nhưng giá tăng), hãy chỉ ra điều đó.
- Mỗi thông tin lấy từ tin tức PHẢI kèm số trích dẫn [1], [2]... theo đúng số của tin trong dữ liệu.
- Không nhắc lại tin không dùng đến.

Định dạng bắt buộc (plain text, không markdown, tiếng Việt):

TỔNG QUAN: 1-2 câu nêu bức tranh chính, kể cả mâu thuẫn nếu có.

💰 Giá & dòng tiền khối ngoại
• 2-4 gạch đầu dòng ngắn, mỗi dòng 1 ý, số liệu cụ thể

📊 Định giá & cơ bản
• 1-2 gạch đầu dòng (P/E, P/B, ROE, vốn hóa...)

📰 Tin đáng chú ý
• 1-3 gạch đầu dòng, mỗi tin kèm [n]

👀 Đáng theo dõi: 1 câu duy nhất.

Nguồn: [n] tên báo, ngày — liệt kê đúng các tin đã trích. Thêm dòng cuối: "Số liệu giá/dòng tiền/định giá: VNDirect."

⚠️ Thông tin tham khảo, không phải khuyến nghị đầu tư."""


def gather(sym, flows):
    sections = {}
    for name, fn in [("DÒNG TIỀN KHỐI NGOẠI 10 PHIÊN", lambda: presenters.format_trend(sym, flows.foreign_daily(sym))),
                     ("GIÁ", lambda: vndirect_api.fetch_prices_text(sym)),
                     ("CHỈ SỐ CƠ BẢN", lambda: vndirect_api.fetch_fundamentals(sym)),
                     ("TIN TỨC GẦN ĐÂY", lambda: news_api.fetch_news(sym))]:
        try:
            sections[name] = fn()
        except Exception as e:
            sections[name] = f"(lỗi khi lấy dữ liệu: {e})"
    return "\n\n".join(f"### {k}\n{v}" for k, v in sections.items())


def build_brief(sym, flows, llm):
    sym = sym.upper()
    context = gather(sym, flows)
    text = llm.complete(SYSTEM, f"Dữ liệu về cổ phiếu {sym} hôm nay:\n\n{context}\n\nViết bản tin.").strip()
    return f"📋 Brief {sym}\n\n{text}"[:4000]  # Telegram cap 4096
