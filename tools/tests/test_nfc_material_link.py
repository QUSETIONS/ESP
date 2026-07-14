from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
NFC_H = (ROOT / "main/boards/zectrix/zectrix_nfc.h").read_text(encoding="utf-8")
NFC_CC = (ROOT / "main/boards/zectrix/zectrix_nfc.cc").read_text(encoding="utf-8")
BOARD = (
    ROOT / "main/boards/zectrix-s3-epaper-4.2/zectrix-s3-epaper-4.2.cc"
).read_text(encoding="utf-8")
MEETING_DATA_CC = (ROOT / "main/meeting/meeting_data.cc").read_text(encoding="utf-8")


def section(source: str, start: str, end: str) -> str:
    return source.split(start, 1)[1].split(end, 1)[0]


def test_nfc_driver_writes_and_reads_back_http_uri_ndef():
    assert "WriteVerifiedUriNdef(const std::string& uri)" in NFC_H
    verified = section(
        NFC_CC,
        "esp_err_t ZectrixNfc::WriteVerifiedUriNdef",
        "void ZectrixNfc::FieldTaskEntry",
    )
    assert '"https://"' in verified
    assert '"http://"' in verified
    assert "BuildUriNdefMessage(uri)" in verified
    assert "WriteNdef(expected)" in verified
    assert "ReadNdef(&actual)" in verified
    assert "actual != expected" in verified
    assert "ESP_ERR_INVALID_RESPONSE" in verified


def test_board_publishes_default_and_updated_material_urls():
    assert "kNfcWriteAttempts = 3" in BOARD
    assert "void SyncNfcMaterialUrl(const std::string& url)" in BOARD
    assert "last_nfc_material_url_" in BOARD
    assert "NFC material URI verified" in BOARD

    init = section(BOARD, "void InitializeNfc()", "void InitializeChargeStatus()")
    ble = section(BOARD, "void CommitMeetingJson", "static bool IsValidMeetingUrlFromBle")
    http = section(BOARD, "bool FetchMeetingDataOnce()", "static void NotesFetchTaskEntry")
    assert "SyncNfcMaterialUrl" in init
    assert "SyncNfcMaterialUrl(data.materials_url)" in ble
    assert "SyncNfcMaterialUrl(data.materials_url)" in http


def test_factory_test_url_is_not_used_by_normal_material_flow():
    normal_flow = section(BOARD, "void SyncNfcMaterialUrl", "void InitializeChargeStatus")
    assert "factory-test" not in normal_flow.lower()
    assert "WriteVerifiedUriNdef" in normal_flow


def test_default_nfc_material_url_is_publicly_downloadable_not_placeholder():
    expected = "https://raw.githubusercontent.com/QUSETIONS/ESP/master/tools/meeting_server/files/materials.txt"
    assert expected in MEETING_DATA_CC
    assert "https://msh.cn/m" not in MEETING_DATA_CC
