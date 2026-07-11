from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_wechat_miniprogram_declares_ble_demo_page():
    app_json = read("tools/wechat_miniprogram/miniprogram/app.json")
    page_json = read("tools/wechat_miniprogram/miniprogram/pages/index/index.json")

    assert "pages/index/index" in app_json
    assert "GoTim Ink" in app_json
    assert "navigationBarTitleText" in page_json


def test_wechat_miniprogram_wires_required_ble_uuids_and_apis():
    source = read("tools/wechat_miniprogram/miniprogram/pages/index/index.js")
    markup = read("tools/wechat_miniprogram/miniprogram/pages/index/index.wxml")

    assert "6E3F0010-2A1B-4F2E-8C5D-1234567890AB" in source
    assert "6E3F0011-2A1B-4F2E-8C5D-1234567890AB" in source
    assert "6E3F0013-2A1B-4F2E-8C5D-1234567890AB" in source
    assert "6E3F0014-2A1B-4F2E-8C5D-1234567890AB" in source
    assert "wx.openBluetoothAdapter" in source
    assert "wx.startBluetoothDevicesDiscovery" in source
    assert "wx.createBLEConnection" in source
    assert "wx.notifyBLECharacteristicValueChange" in source
    assert "wx.writeBLECharacteristicValue" in source
    assert "sendProvision" in source
    assert "encodeMeetingFrames" in source
    assert "sendMeeting" in source
    assert "normalizeUuid" in source
    assert "discoverGotimService" in source
    assert "findCharacteristic" in source
    assert "services: [SERVICE_UUID]" not in source
    assert "allowDuplicatesKey: true" in source
    assert "serviceId: this.data.serviceId" in source
    assert "meetingCharacteristicId" in source
    assert "statusCharacteristicId" in source
    assert "provisionCharacteristicId" in source
    assert "serverUrl" in source
    assert "wx.request" in source
    assert "syncMeetingToServer" in source
    assert "fetchMeetingFromServer" in source
    assert "sendTranscriptDemo" in source
    assert "/meeting/current" in source
    assert "/meeting/transcript" in source
    assert "bindtap=\"syncMeetingToServer\"" in markup
    assert "bindtap=\"fetchMeetingFromServer\"" in markup
    assert "bindtap=\"sendTranscriptDemo\"" in markup


def test_wechat_miniprogram_readme_documents_ios_demo_flow():
    readme = read("tools/wechat_miniprogram/README.md")

    assert "微信开发者工具" in readme
    assert "2.4GHz" in readme
    assert "Provision" in readme
    assert "Meeting" in readme
    assert "Status" in readme
    assert "meeting_server.py" in readme
    assert "/meeting/transcript" in readme
