from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_board_falls_back_to_browser_config_ap_when_station_cannot_connect():
    board = read("main/boards/zectrix-s3-epaper-4.2/zectrix-s3-epaper-4.2.cc")

    assert "kWifiConfigFallbackMs" in board
    assert "StartWifiConfigFallbackTask" in board
    assert "WifiConfigFallbackTask" in board
    assert "wifi.StartConfigAp()" in board
    assert "Wi-Fi station fallback to config AP" in board
    assert "wifi_fallback_task_" in board


def test_no_wechat_browser_route_is_documented():
    doc = read("tools/no_wechat_demo/README.md")

    assert "不用微信小程序" in doc
    assert "ZecTrix" in doc
    assert "192.168.4.1" in doc
    assert "http://10.63.7.152:8787/meeting/current" in doc
    assert "浏览器" in doc
