"""Headless-browser smoke test (needs: pip install playwright). Usage: python3 tests/ui.py http://localhost:8765 owner@salon.local TestPass123"""
import sys, re
from playwright.sync_api import sync_playwright
BASE, EMAIL, PW = sys.argv[1:4]
errors = []
with sync_playwright() as p:
    b = p.chromium.launch()
    ctx = b.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=2)
    pg = ctx.new_page()
    pg.on("pageerror", lambda e: errors.append("PAGEERROR " + str(e)))
    pg.on("console", lambda m: errors.append("CONSOLE " + m.text) if m.type == "error" and "fonts.g" not in m.text and "ERR_" not in m.text and "Failed to load resource" not in m.text else None)
    pg.on("response", lambda r: errors.append("HTTP %d %s" % (r.status, r.url)) if r.status >= 400 and "/api/" in r.url else None)
    def visit(h, wait=700, shot=None):
        pg.goto(BASE + "/#" + h); pg.wait_for_timeout(wait)
        txt = pg.inner_text("body")
        if "couldn’t load" in txt: errors.append("LOAD FAIL " + h + " :: " + txt[:200])
        if shot: pg.screenshot(path="/tmp/shots/" + shot + ".png", full_page=False)
        return txt
    import os; os.makedirs("/tmp/shots", exist_ok=True)
    visit("/", 1200, "home")
    for h in ["/about", "/services", "/services/5", "/staff", "/products", "/promotions", "/reviews", "/location", "/contact", "/chat/ai", "/chat/salon", "/login", "/account/profile", "/nope"]:
        visit(h)
    # AI chat through UI
    visit("/chat/ai"); pg.fill("#in", "Open ba kayo Sunday?"); pg.press("#in", "Enter"); pg.wait_for_timeout(900)
    assert "every Sunday from 10:00 AM to 10:00 PM" in pg.inner_text("#msgs"), "AI reply missing"
    pg.screenshot(path="/tmp/shots/ai.png")
    # booking through UI
    visit("/book?service=5", 900)
    assert "Choose your services" in pg.inner_text("body")
    pg.click("#next"); pg.wait_for_timeout(300)
    pg.click(".day >> nth=1"); pg.wait_for_selector(".slot", timeout=4000); pg.click(".slot >> nth=2"); pg.screenshot(path="/tmp/shots/book2.png"); pg.click("#next")
    pg.fill("[name=name]", "UI Tester"); pg.fill("[name=phone]", "+971501234567"); pg.click("button:has-text('Review booking')"); pg.wait_for_timeout(200)
    pg.screenshot(path="/tmp/shots/book4.png"); pg.click("#ok"); pg.wait_for_selector("text=Reference", timeout=4000)
    print("booking via UI ok:", re.search(r"BM-\w+", pg.inner_text("body")).group(0))
    # register customer, account pages
    visit("/login?mode=register"); pg.fill("[name=name]", "Ui Customer"); pg.fill("[name=phone]", "+971500000001"); pg.fill("[name=email]", "ui@example.com"); pg.fill("[name=password]", "password123"); pg.click("#af button.btn"); pg.wait_for_timeout(1200)
    for t in ["appointments", "reviews", "messages", "notifications", "settings", "profile"]:
        visit("/account/" + t)
    visit("/chat/salon"); pg.fill("#in", "Hi, available po ba si Elma tomorrow?"); pg.press("#in", "Enter"); pg.wait_for_timeout(900)
    visit("/reviews"); pg.click("#write"); pg.wait_for_timeout(300); pg.screenshot(path="/tmp/shots/review.png")
    pg.click("#starpick label >> nth=4"); pg.fill("textarea[name=body]", "Lovely salon, great service."); pg.click("button:has-text('Submit review')"); pg.wait_for_timeout(900)
    # customer cannot reach admin
    visit("/admin/revenue"); assert "sign in" in pg.inner_text("body").lower() or "staff only" in pg.inner_text("body").lower(), "customer saw admin"
    pg.click("text=Sign out") if pg.query_selector("text=Sign out") else None
    ctx2 = b.new_context(viewport={"width": 1280, "height": 860}); pg2 = ctx2.new_page()
    pg2.on("pageerror", lambda e: errors.append("ADMIN PAGEERROR " + str(e)))
    pg2.on("response", lambda r: errors.append("ADMIN HTTP %d %s" % (r.status, r.url)) if r.status >= 400 and "/api/" in r.url else None)
    pg2.goto(BASE + "/#/admin"); pg2.wait_for_timeout(600)
    assert "Owner & staff sign in" in pg2.inner_text("body")
    pg2.fill("[name=email]", EMAIL); pg2.fill("[name=password]", PW); pg2.click("#lf button.btn"); pg2.wait_for_timeout(1500)
    pg2.screenshot(path="/tmp/shots/admin_dash.png")
    for h in ["", "/appointments", "/customers", "/services", "/service-categories", "/staff", "/products", "/product-categories", "/promotions", "/reviews", "/testimonials", "/messages", "/notifications", "/revenue", "/analytics", "/settings/business", "/settings/hours", "/settings/lists", "/settings/images", "/settings/booking", "/settings/integrations", "/closures", "/ai"]:
        pg2.goto(BASE + "/#/admin" + h); pg2.wait_for_timeout(700)
        t = pg2.inner_text("body")
        if "couldn’t load" in t or "Owner access only" in t: errors.append("ADMIN LOAD FAIL " + h + " " + t[:150])
        if h in ("/appointments", "/revenue", "/services"): pg2.screenshot(path="/tmp/shots/admin%s.png" % h.replace("/", "_"))
    # open appointment dialog + complete flow
    pg2.goto(BASE + "/#/admin/appointments"); pg2.wait_for_timeout(800); pg2.click("tr.click >> nth=0"); pg2.wait_for_timeout(400)
    pg2.screenshot(path="/tmp/shots/admin_appt.png")
    pg2.click("[data-complete]"); pg2.wait_for_timeout(300)
    pg2.fill("[data-item]", "150"); pg2.select_option("[name=method]", "Apple Pay"); pg2.screenshot(path="/tmp/shots/admin_complete.png")
    pg2.click("text=Complete appointment"); pg2.wait_for_timeout(1200)
    pg2.goto(BASE + "/#/admin/revenue"); pg2.wait_for_timeout(1200); pg2.screenshot(path="/tmp/shots/admin_revenue_after.png")
    body = pg2.inner_text("body"); assert "AED 150.00" in body, "revenue not updated: " + body[:400]
    print("revenue shows AED 150.00 after UI completion")
    b.close()
print("\n".join(errors) if errors else "NO ERRORS")
sys.exit(1 if errors else 0)
