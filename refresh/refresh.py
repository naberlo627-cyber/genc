#!/usr/bin/env python3
"""Genç veri yenileme servisi — tek işi etkinlik verisini güncel tutmak.

Bu betik etkinlik verisini kaynaklardan yeniden toplar, zenginleştirir, yayına
hazır hâle getirir ve sonucu raporlar. Başka hiçbir iş yapmaz.

Ne yapar (sırayla):
  1. Toplama   : tools/collect_tickets.py  → data/tickets.json
  2. Zenginleştirme: tools/enrich_events.py → açıklama/kadro/kural alanları
  3. Yayın yükü: tools/build_payload.py    → data/cities/*.json + data/index.json
  4. Gömme     : tools/embed_data.py       → Genc.html içine yedek veri (APK için)
  5. Durum     : data/refresh_status.json (son çalışma, süre, sayı, hata)

Uygulama açılışta yalnızca seçili ilin dosyasını (data/cities/<il>.json) çeker;
tüm illeri tek dosyada indirmez.

Kapsam dışı: APK sürümü (version.json) ve önbellek sürümü (sw.js) artırmaz.
APK sürümü yalnızca gerçek bir uygulama derlemesiyle artırılır.

Tasarım ilkeleri:
  * Asla çökmez: her adım hataya dayanıklıdır, hata olsa da çalışma kaydı yazılır
    ve çıkış kodu anlamlı olur (0 başarı, 1 hata).
  * Eşzamanlılık güvenli: kilit dosyası ile aynı anda iki çalışma engellenir.
  * Tekrar çalıştırılabilir: kısmi veri yayına alınmaz; başarısızsa önceki veri
    olduğu gibi kalır.
  * Sessizce bozmaz: kaynaklar az/boş dönerse yeni veri yayına alınmaz, eski veri
    korunur ve durum dosyasına "reddedildi" yazılır.

Kullanım:
    python3 refresh/refresh.py                 # tam yenileme
    python3 refresh/refresh.py --dry-run       # toplamadan sadece akışı denetle
    python3 refresh/refresh.py --limit 120     # kaynak başına detay sınırı (0 = sınırsız)
    python3 refresh/refresh.py --min-events 50 # yayın için en az etkinlik sayısı
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
TICKETS = DATA / "tickets.json"
EVENTS = DATA / "events.json"
STATUS = DATA / "refresh_status.json"
LOCK = ROOT / "refresh" / ".lock"
LOG_DIR = ROOT / "refresh" / "logs"

# Boş = tüm iller (kaynaklar 81 ili de tarar).
CITIES = ""


def log(msg: str) -> None:
    stamp = time.strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{stamp}] {msg}"
    print(line, flush=True)
    try:
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        with open(LOG_DIR / "refresh.log", "a", encoding="utf-8") as fh:
            fh.write(line + "\n")
    except OSError:
        pass


def write_status(**fields) -> None:
    """Durum dosyasını atomik olarak yazar; uygulama ve izleme bunu okur."""
    try:
        prev = json.loads(STATUS.read_text(encoding="utf-8")) if STATUS.exists() else {}
    except Exception:
        prev = {}
    prev.update(fields)
    prev["updated_at"] = time.strftime("%Y-%m-%dT%H:%M:%S%z")
    tmp = STATUS.with_suffix(".tmp")
    tmp.write_text(json.dumps(prev, ensure_ascii=False, indent=1), encoding="utf-8")
    os.replace(tmp, STATUS)


class LockBusy(RuntimeError):
    pass


def acquire_lock() -> None:
    """Basit kilit: eski (yarıdan fazla gün) kilit dosyası sahipsiz sayılır."""
    if LOCK.exists():
        age = time.time() - LOCK.stat().st_mtime
        if age > 20 * 3600:
            log(f"eski kilit temizlendi ({age/3600:.1f} sa)")
            LOCK.unlink(missing_ok=True)
        else:
            raise LockBusy(f"başka bir yenileme çalışıyor (kilit {age/60:.1f} dk önce)")
    LOCK.write_text(str(os.getpid()), encoding="utf-8")


def release_lock() -> None:
    LOCK.unlink(missing_ok=True)


def run(cmd: list[str], timeout: int) -> tuple[bool, str]:
    """Alt süreci çalıştırır; çıktının son satırlarını döner. Asla exception atmaz."""
    try:
        res = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return False, f"zaman aşımı ({timeout}s)"
    except Exception as exc:  # noqa: BLE001 - dış süreç her türlü hata verebilir
        return False, f"çalıştırılamadı: {exc}"
    out = (res.stdout or "").strip().splitlines()
    tail = " | ".join(out[-3:]) if out else ""
    if res.returncode != 0:
        err = (res.stderr or "").strip().splitlines()
        return False, f"çıkış {res.returncode}: {(err[-1] if err else tail)}"
    return True, tail


def count_events(path: Path) -> int:
    try:
        return len(json.loads(path.read_text(encoding="utf-8")).get("events", []))
    except Exception:
        return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0, help="kaynak başına detay sınırı (0 = sınırsız)")
    ap.add_argument("--min-events", type=int, default=80, help="yayın için en az etkinlik sayısı")
    ap.add_argument("--dry-run", action="store_true", help="toplamadan akışı denetle")
    ap.add_argument("--timeout", type=int, default=1800, help="adım başına zaman aşımı (sn)")
    args = ap.parse_args()

    started = time.time()
    before = count_events(EVENTS)
    log(f"yenileme başladı (limit={args.limit}, önceki={before} etkinlik)")

    try:
        acquire_lock()
    except LockBusy as exc:
        log(f"ATLANDI: {exc}")
        return 0

    steps = [
        ("toplama", [sys.executable, "tools/collect_tickets.py", "--sehir", CITIES, "--limit", str(args.limit)]),
        # Tekrar denetimi toplamadan hemen sonra: birleştirme bozulduysa
        # zenginleştirmeye/zengin veriye hiç geçilmez.
        ("tekrar denetimi", [sys.executable, "tools/tekrar_denetimi.py"]),
        ("zenginleştirme", [sys.executable, "tools/enrich_events.py"]),
        ("metin temizleme", [sys.executable, "tools/clean_events.py"]),
        # İlçe adları yayın yükünden önce doğrulanır: kaynak siteler semt ya da
        # başka ilin ilçesini yazabiliyor ve kayıt yanlış süzgece düşüyordu.
        ("ilçe düzeltme", [sys.executable, "tools/fix_districts.py"]),
        ("yayın yükü", [sys.executable, "tools/build_payload.py"]),
        ("gömme", [sys.executable, "tools/embed_data.py"]),
        # Denetim son adımdır: yayın zaten hazır. Kaynak bozulmuşsa yalnızca
        # durum dosyasına yazılır, akış durdurulmaz (eski veri korunur).
        ("kaynak denetimi", [sys.executable, "tools/kaynak_denetimi.py"]),
    ]

    try:
        if args.dry_run:
            log("deneme (dry-run): adımlar çalıştırılmadı, durum dosyasına yazılmadı")
            return 0

        for name, cmd in steps:
            t0 = time.time()
            ok, tail = run(cmd, args.timeout)
            dt = round(time.time() - t0, 1)
            if not ok and name == "kaynak denetimi":
                log(f"! {name}: kaynak sorunları bildirildi ({dt}s): {tail}")
                continue
            if not ok:
                log(f"✗ {name} başarısız ({dt}s): {tail}")
                write_status(last_run={"started": started, "ok": False, "step": name,
                                       "error": tail, "events": before,
                                       "duration": round(time.time() - started, 1)})
                return 1
            log(f"✓ {name} ({dt}s): {tail}")

        after = count_events(TICKETS)
        if after < args.min_events:
            log(f"✗ yayınlanan veri çok az ({after} < {args.min_events}); önceki veri korunuyor")
            write_status(last_run={"started": started, "ok": False, "step": "doğrulama",
                                   "error": f"yetersiz etkinlik: {after}",
                                   "events": after, "duration": round(time.time() - started, 1)})
            return 1

        cities = json.loads(TICKETS.read_text(encoding="utf-8")).get("cities", [])
        duration = round(time.time() - started, 1)
        log(f"✓ tamamlandı: {after} etkinlik, {len(cities)} il ({duration}s)")
        write_status(last_run={"started": started, "ok": True, "events": after,
                               "cities": cities, "duration": duration},
                     last_success=time.strftime("%Y-%m-%dT%H:%M:%S%z"),
                     last_success_events=after)
        return 0
    finally:
        release_lock()


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        release_lock()
        sys.exit(130)
