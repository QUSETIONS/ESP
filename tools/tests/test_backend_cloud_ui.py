from html.parser import HTMLParser

from tools.meeting_server import meeting_server


class _EditorStructureParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.stack: list[set[str]] = []
        self.ancestors_by_id: dict[str, set[str]] = {}

    def handle_starttag(self, tag, attrs):
        values = dict(attrs)
        classes = set(values.get("class", "").split())
        inherited = set().union(*self.stack) if self.stack else set()
        current = inherited | classes
        if element_id := values.get("id"):
            self.ancestors_by_id[element_id] = current
        if tag not in {"input", "meta", "link", "br", "hr"}:
            self.stack.append(classes)

    def handle_endtag(self, tag):
        if tag not in {"input", "meta", "link", "br", "hr"} and self.stack:
            self.stack.pop()


def test_editor_exposes_cloud_device_status_and_action():
    html = meeting_server.EDITOR_HTML

    for marker in (
        'id="zectrixConnection"',
        'id="zectrixDevices"',
        "checkZectrixIntegration",
        "/api/integrations/zectrix",
        "ZECTRIX_API_KEY_FILE",
    ):
        assert marker in html


def test_editor_exposes_aggregated_control_plane_status():
    html = meeting_server.EDITOR_HTML

    for marker in (
        'id="controlPlane"',
        'id="overviewMeeting"',
        'id="overviewTranscript"',
        'id="overviewNotes"',
        'id="overviewCloud"',
        'id="overviewFleet"',
        "loadOverview",
        'fetchJson("/api/overview")',
        "setInterval",
    ):
        assert marker in html

def test_editor_keeps_all_basic_fields_inside_responsive_grid():
    parser = _EditorStructureParser()
    parser.feed(meeting_server.EDITOR_HTML)

    assert "grid2" in parser.ancestors_by_id["reminderUrl"]
    assert "grid2" in parser.ancestors_by_id["agendaIndex"]


def test_editor_mobile_chrome_prioritizes_actions_over_endpoint_metadata():
    html = meeting_server.EDITOR_HTML

    assert 'id="status" class="status" role="status"' in html
    assert ".status::before" in html
    assert ".panelHead > span { display: none; }" in html
    assert "操作口径" not in html
