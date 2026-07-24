"""Rule thuan: nhan so, tra quyet dinh. Khong IO, khong import config."""
import statistics

from .entities import TrendStats


def classify_regime(day_net, recent, factor, day_net_th, rate_th, exit_th=None):
    """exit_th (bible §2): nguong XA rieng, thap hon day_net_th -> thoat nhay hon vao. None -> doi xung."""
    exit_th = day_net_th if exit_th is None else exit_th
    if day_net >= day_net_th * factor:
        return "GOM" if recent > rate_th * factor else "GOM_CHUNG"
    if day_net <= -exit_th * factor:
        return "XA" if recent < -rate_th * factor else "XA_CHUNG"
    return "NEUTRAL"


def spike_share(net, win_value, day_value, factor, min_day_value, min_net, min_share, min_day_share=0.0):
    """min_day_share (bible §5.2): net phai >= min_day_share * GTGD ngay -> 'dang ke so voi chinh ma',
    khong chi ap dao 1 window mong. min_day_share=0 -> tat gate (default an toan)."""
    if (day_value < min_day_value * factor or abs(net) < min_net * factor
            or abs(net) < min_day_share * day_value * factor or win_value <= 0):
        return None
    share = abs(net) / win_value
    return share if share >= min_share else None


def is_accel(d1, d2, d3, win3, day_value, factor, min_day_value, min_last, min_share):
    same_sign = (d1 > 0 and d2 > 0 and d3 > 0) or (d1 < 0 and d2 < 0 and d3 < 0)
    if day_value < min_day_value * factor or not same_sign or abs(d3) < min_last * factor:
        return False
    if not (abs(d1) < abs(d2) < abs(d3)):
        return False
    return win3 > 0 and abs(d3) / win3 >= min_share


def is_locked(day_value, prev_day_value, share_th):
    """San cung: GTGD nhip nay tang < share_th * tong ngay -> du ban san khong khop (mat thanh khoan)."""
    if prev_day_value is None or day_value <= 0:
        return False
    return (day_value - prev_day_value) < share_th * day_value


def trend_stats(nets):
    """Phan tich chuoi phien. Precondition: nets khong rong — caller (presenter) guard truoc."""
    cum, buys = sum(nets), sum(v > 0 for v in nets)
    last3 = tuple(nets[-3:])
    a3 = sum(last3) / len(last3)
    rest = nets[:-3] or [0]
    a_rest = sum(rest) / len(rest)
    # median: 1 phien dot bien (thoa thuan) khong duoc phep tu minh tao nhan dao chieu
    if cum != 0 and statistics.median(last3) * cum < 0:
        momo = "DAO_CHIEU"
    elif abs(a3) > 1.5 * abs(a_rest):
        momo = "MANH"
    elif abs(a3) < 0.5 * abs(a_rest):
        momo = "YEU"
    else:
        momo = "ON_DINH"
    streak = 1
    for v in reversed(nets[:-1]):
        if v * nets[-1] > 0:
            streak += 1
        else:
            break
    streak_side = "mua" if nets[-1] > 0 else "bán"
    flipped = len(nets) > 1 and nets[-1] * nets[-2] < 0
    return TrendStats(cum=cum, buys=buys, last3=last3, momo=momo,
                      streak=streak, streak_side=streak_side, flipped=flipped)
