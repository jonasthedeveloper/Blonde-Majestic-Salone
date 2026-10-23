"""Revenue engine. Every figure is computed from the payments/appointments tables at request time.

Recognised income = payment.status 'paid' AND appointment.status 'completed', minus any refunded amount.
Pending, voided, fully refunded, cancelled and no-show transactions never count.
Per-service / category / staff figures allocate a payment's amounts across its items in proportion to item price.
"""
import datetime as dt, csv, io
from . import db
from .booking import now_local
from .web import ApiError, DATE_RX


def resolve_range(preset, d_from=None, d_to=None):
    today = now_local().date()
    if preset == "today":
        return today, today
    if preset == "yesterday":
        y = today - dt.timedelta(days=1)
        return y, y
    if preset == "week":
        s = today - dt.timedelta(days=today.weekday())
        return s, s + dt.timedelta(days=6)
    if preset == "month":
        s = today.replace(day=1)
        nxt = (s.replace(day=28) + dt.timedelta(days=4)).replace(day=1)
        return s, nxt - dt.timedelta(days=1)
    if preset == "year":
        return today.replace(month=1, day=1), today.replace(month=12, day=31)
    if preset == "custom":
        if not (DATE_RX.match(d_from or "") and DATE_RX.match(d_to or "")):
            raise ApiError(400, "Please choose both a start and an end date.")
        a, b = dt.date.fromisoformat(d_from), dt.date.fromisoformat(d_to)
        if a > b:
            raise ApiError(400, "The start date must be before the end date.")
        return a, b
    return None, None  # all time


def _r(x):
    return round(x + 1e-9, 2)


def collect(preset=None, d_from=None, d_to=None, category_id=None, staff_id=None, service_id=None, method=None):
    a, b = resolve_range(preset, d_from, d_to)
    q = ("SELECT p.*, a.ref, a.date AS appt_date, a.start_time AS appt_time, a.customer_name, a.status AS appt_status, pr.title AS promo_title "
         "FROM payments p JOIN appointments a ON a.id=p.appointment_id LEFT JOIN promotions pr ON pr.id=a.promo_id WHERE 1=1")
    args = []
    if a:
        q += " AND substr(COALESCE(p.paid_at,p.created),1,10) BETWEEN ? AND ?"
        args += [a.isoformat(), b.isoformat()]
    if method:
        q += " AND p.method=?"
        args.append(method)
    pays = db.all(q + " ORDER BY COALESCE(p.paid_at,p.created) DESC", args)
    rows, txs = [], []
    for p in pays:
        items = db.all("SELECT i.*, st.name AS staff_name, c.name AS category_name FROM appointment_items i LEFT JOIN staff st ON st.id=i.staff_id "
                       "LEFT JOIN categories c ON c.id=i.category_id WHERE appointment_id=? ORDER BY start_time", (p["appointment_id"],))
        if not items:
            continue
        recognised = p["status"] == "paid" and p["appt_status"] == "completed"
        w = [i["price"] or 0 for i in items]
        if sum(w) <= 0:
            w = [1] * len(items)
        tot, rem = sum(w), {"g": p["gross"], "d": p["discount"], "n": (p["net"] - p["refunded_amount"]) if recognised else 0.0}
        prow = []
        for k, i in enumerate(items):
            last = k == len(items) - 1
            sh = w[k] / tot
            g = rem["g"] if last else _r(p["gross"] * sh)
            d = rem["d"] if last else _r(p["discount"] * sh)
            n = rem["n"] if last else _r(((p["net"] - p["refunded_amount"]) if recognised else 0.0) * sh)
            rem["g"] -= g; rem["d"] -= d; rem["n"] -= n
            r = {"payment_id": p["id"], "service_id": i["service_id"], "service": i["service_name"], "category_id": i["category_id"],
                 "category": i["category_name"] or "Uncategorised", "staff_id": i["staff_id"], "staff": i["staff_name"] or "Unassigned",
                 "gross": _r(g), "discount": _r(d), "net": _r(n), "recognised": recognised, "method": p["method"] or "-"}
            prow.append(r)
        sel = [r for r in prow if (not category_id or r["category_id"] == category_id) and (not staff_id or r["staff_id"] == staff_id)
               and (not service_id or r["service_id"] == service_id)]
        if not sel:
            continue
        rows += sel
        label = "Completed" if recognised else ("Paid" if p["status"] == "paid" else p["status"].capitalize())
        txs.append({"id": p["id"], "appointment_id": p["appointment_id"], "ref": p["ref"], "customer": p["customer_name"], "appt_date": p["appt_date"], "appt_time": p["appt_time"],
                    "services": ", ".join(i["service_name"] for i in items), "staff": ", ".join(sorted({i["staff_name"] or "Unassigned" for i in items})),
                    "gross": p["gross"], "discount": p["discount"], "promo": p["promo_title"] or "", "net": p["net"], "refunded": p["refunded_amount"],
                    "income": _r(sum(r["net"] for r in sel)), "method": p["method"] or "-", "status": p["status"], "status_label": label,
                    "counts_as_income": recognised, "paid_at": p["paid_at"], "reason": p["reason"]})
    rec = [r for r in rows if r["recognised"]]
    paid_ids = {r["payment_id"] for r in rec}
    income = _r(sum(r["net"] for r in rec))
    out = {
        "range": {"from": a.isoformat() if a else None, "to": b.isoformat() if b else None},
        "totals": {"gross": _r(sum(r["gross"] for r in rec)), "discounts": _r(sum(r["discount"] for r in rec)), "income": income,
                   "transactions": len(paid_ids), "services": len(rec), "average": _r(income / len(paid_ids)) if paid_ids else 0.0,
                   "refunded": _r(sum(t["refunded"] for t in txs if t["status"] in ("paid", "refunded"))),
                   "pending": _r(sum(t["net"] for t in txs if t["status"] == "pending")),
                   "pending_count": sum(1 for t in txs if t["status"] == "pending")},
        "transactions": txs,
    }
    for key, field in (("by_method", "method"), ("by_category", "category"), ("by_service", "service"), ("by_staff", "staff")):
        agg = {}
        for r in rec:
            x = agg.setdefault(r[field], {"name": r[field], "gross": 0.0, "discount": 0.0, "net": 0.0, "pids": set(), "count": 0})
            x["gross"] += r["gross"]; x["discount"] += r["discount"]; x["net"] += r["net"]; x["pids"].add(r["payment_id"]); x["count"] += 1
        out[key] = sorted([{"name": x["name"], "gross": _r(x["gross"]), "discount": _r(x["discount"]), "net": _r(x["net"]),
                            "transactions": len(x["pids"]), "services": x["count"],
                            "share": _r(100 * x["net"] / income) if income else 0} for x in agg.values()], key=lambda z: -z["net"])
    day = {}
    for t in txs:
        if t["counts_as_income"] and t["paid_at"]:
            day[t["paid_at"][:10]] = day.get(t["paid_at"][:10], 0) + t["income"]
    out["by_day"] = [{"date": k, "income": _r(v)} for k, v in sorted(day.items())]
    return out


def summary_cards():
    return {p: collect(p)["totals"] for p in ("today", "week", "month", "year")} | {"all": collect(None)["totals"]}


def to_csv(data, title="Revenue report"):
    f = io.StringIO()
    w = csv.writer(f)
    w.writerow([title])
    w.writerow(["Period", data["range"]["from"] or "All time", data["range"]["to"] or ""])
    w.writerow(["Generated", db.now_str()])
    w.writerow([])
    t = data["totals"]
    for lab, key in (("Total gross service amount", "gross"), ("Discounts", "discounts"), ("Net amount actually paid (total income)", "income"),
                     ("Completed transactions", "transactions"), ("Average transaction value", "average"), ("Refunded", "refunded")):
        w.writerow([lab, t[key]])
    for title2, key in (("Payment method breakdown", "by_method"), ("Service category breakdown", "by_category"), ("Service breakdown", "by_service"), ("Staff revenue contribution", "by_staff")):
        w.writerow([]); w.writerow([title2]); w.writerow(["Name", "Transactions", "Gross", "Discount", "Net income", "Share %"])
        for x in data[key]:
            w.writerow([x["name"], x["transactions"], x["gross"], x["discount"], x["net"], x["share"]])
    w.writerow([]); w.writerow(["Transactions"])
    w.writerow(["Reference", "Customer", "Appointment date", "Services", "Staff", "Original price", "Discount", "Promotion", "Amount paid", "Refunded", "Income counted", "Method", "Status", "Paid at"])
    for x in data["transactions"]:
        w.writerow([x["ref"], x["customer"], x["appt_date"], x["services"], x["staff"], x["gross"], x["discount"], x["promo"], x["net"], x["refunded"], x["income"] if x["counts_as_income"] else 0, x["method"], x["status_label"], x["paid_at"] or ""])
    return "\ufeff" + f.getvalue()
