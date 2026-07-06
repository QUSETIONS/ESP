from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def read(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8")


def test_wifi_portal_exposes_meeting_url_field():
    html = read("main/components/78__esp-wifi-connect/assets/wifi_configuration.html")

    assert 'id="meeting_url"' in html
    assert "meeting_url:" in html
    assert "document.getElementById('meeting_url').value" in html


def test_wifi_config_backend_persists_meeting_url():
    source = read("main/components/78__esp-wifi-connect/wifi_configuration_ap.cc")

    assert '"meeting_url"' in source
    assert "nvs_get_str(nvs, kMeetingUrlKey" in source
    assert "nvs_set_str(nvs, kMeetingUrlKey" in source
    assert 'cJSON_AddStringToObject(json, "meeting_url"' in source


def test_meeting_fetch_uses_runtime_configured_url():
    board_source = read("main/boards/zectrix-s3-epaper-4.2/zectrix-s3-epaper-4.2.cc")
    cmake = read("main/CMakeLists.txt")

    assert '#include "meeting/meeting_config.h"' in board_source
    assert "GetMeetingAssistantUrl()" in board_source
    assert "const char* url = CONFIG_MEETING_ASSISTANT_URL;" not in board_source
    assert '"meeting/meeting_config.cc"' in cmake
