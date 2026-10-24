#!/usr/bin/env python3
# <bitbar.title>OpenCode GO & OpenAI v6 Fleet Monitor</bitbar.title>
# <bitbar.version>v1.0</bitbar.version>
# <bitbar.author>Antigravity</bitbar.author>
# <bitbar.desc>Real-time 5h rolling quota and monthly spend monitor for v6 models</bitbar.desc>
# <bitbar.dependencies>python3</bitbar.dependencies>

import urllib.request
import json
import sys

URL = "http://localhost:7890/api/status"

def main():
    try:
        req = urllib.request.Request(URL, headers={"User-Agent": "SwiftBarMonitor"})
        with urllib.request.urlopen(req, timeout=1.5) as r:
            data = json.loads(r.read().decode("utf-8"))
    except Exception:
        print("⚠️ v6 Monitor: Offline")
        print("---")
        print("Szerver nem fut (http://localhost:7890)")
        print("Indítás: ./start.sh | bash=true")
        return

    models = {m["id"]: m for m in data.get("models", [])}
    alerts = data.get("alerts", [])

    # Menu bar top text
    argon = models.get("gemini-4-argon", {})
    mimo = models.get("mimo-v2-6-pro", {})
    sol = models.get("sol-6-1-high", {})

    status_icon = "🟢" if len(alerts) == 0 else "🔴"
    argon_pct = f"{argon.get('pct_5h', 0):.0f}%" if argon else "-"
    mimo_pct = f"{mimo.get('pct_5h', 0):.0f}%" if mimo else "-"
    sol_pct = f"{sol.get('pct_5h', 0):.0f}%" if sol else "-"

    print(f"{status_icon} v6: Sol {sol_pct} | Argon {argon_pct} | MiMo {mimo_pct}")
    print("---")

    # Header & Web Dashboard Link
    print("🌐 Nyisd meg a Web Dashboardot | href=http://localhost:7890 font=HelveticaNeue-Bold color=#6366f1")
    print(f"🕒 Rendszeridő: {data.get('server_time', '')} | size=11 color=#64748b")
    print("---")

    # Alerts section
    if alerts:
      print("⚠️ AKTÍV ESZKALÁCIÓS RIASZTÁSOK: | color=#ef4444 font=HelveticaNeue-Bold")
      for a in alerts:
          print(f"• {a['model']}: {a['msg']} | color=#f87171 size=11")
      print("---")

    # Models list
    for m in data.get("models", []):
        name = m["name"]
        role = m["role"]
        pct_5h = m["pct_5h"]
        pct_usd = m["pct_usd"]
        is_unlimited = m["is_unlimited_5h"]

        dot = "🟢" if m["risk"] == "NORMAL" else ("🟡" if m["risk"] == "WARNING" else "🔴")
        
        if is_unlimited:
            val_str = "∞ Korlátlan"
        else:
            val_str = f"{m['current_req_5h']}/{m['limit_5h_req']} req (5h: {pct_5h}%) • Havi: ${m['current_spent_usd']:.2f} ({pct_usd}%)"

        print(f"{dot} {name} [{role.split()[0]}] | size=12 font=JetBrainsMono-Bold")
        print(f"-- {val_str} | size=11 color=#94a3b8")
        if not is_unlimited and m.get("reset_mins", 0) > 0:
            print(f"-- Reset: ~{m['reset_mins']//60}ó {m['reset_mins']%60}p múlva | size=10 color=#64748b")
        print(f"-- Tartalék: {m['escalation_target']} | size=10 color=#38bdf8")

    print("---")
    print("Frissítés most | refresh=true")

if __name__ == "__main__":
    main()
