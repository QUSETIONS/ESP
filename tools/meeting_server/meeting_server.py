#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import json
import mimetypes
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlparse

try:
    from .note_store import NoteValidationError, VersionConflictError, VersionedNoteStore
    from .realtime_summary import RecordingManager, SequenceGapError, VersionedMeetingStore, format_sse
except ImportError:
    from note_store import NoteValidationError, VersionConflictError, VersionedNoteStore
    from realtime_summary import RecordingManager, SequenceGapError, VersionedMeetingStore, format_sse


ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = ROOT.parents[1]
SEED_DATA = PROJECT_ROOT / "tools" / "meeting_data" / "meeting_current.json"
DEFAULT_DATA = ROOT / "state" / "meeting_current.json"
DEFAULT_FILES = ROOT / "files"
DEFAULT_NOTES = ROOT / "state" / "notes.json"

EDITOR_HTML = r"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>GoTim Ink Meeting Console</title>
  <style>
    :root {
      --paper: #f7f4ea;
      --surface: #fffdf7;
      --ink: #1d1d1b;
      --muted: #6d6b62;
      --line: #d7d0bd;
      --green: #1f7a5b;
      --red: #b44a3a;
      --blue: #345f8a;
      --shadow: 0 18px 38px rgba(40, 37, 28, 0.12);
    }

    * {
      box-sizing: border-box;
    }

    body {
      margin: 0;
      background:
        linear-gradient(90deg, rgba(29, 29, 27, 0.035) 1px, transparent 1px) 0 0 / 20px 20px,
        linear-gradient(0deg, rgba(29, 29, 27, 0.03) 1px, transparent 1px) 0 0 / 20px 20px,
        var(--paper);
      color: var(--ink);
      font-family: ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      letter-spacing: 0;
    }

    button,
    input,
    textarea {
      font: inherit;
    }

    button:focus-visible,
    input:focus-visible,
    textarea:focus-visible {
      outline: 3px solid rgba(31, 122, 91, 0.22);
      outline-offset: 2px;
    }

    .app {
      width: min(1180px, calc(100% - 28px));
      margin: 0 auto;
      padding: 18px 0 28px;
    }

    .topbar {
      display: grid;
      grid-template-columns: minmax(0, 1fr) auto;
      gap: 14px;
      align-items: end;
      padding: 0 0 14px;
      border-bottom: 2px solid var(--ink);
    }

    .brand {
      display: flex;
      align-items: center;
      gap: 12px;
      min-width: 0;
    }

    .mark {
      display: grid;
      place-items: center;
      width: 40px;
      height: 40px;
      border: 2px solid var(--ink);
      background: var(--surface);
      box-shadow: 4px 4px 0 var(--ink);
      font-weight: 900;
    }

    h1 {
      margin: 0;
      font-size: clamp(20px, 3.5vw, 34px);
      line-height: 1.05;
      letter-spacing: 0;
    }

    .subtitle {
      margin: 5px 0 0;
      color: var(--muted);
      font-size: 13px;
    }

    .status {
      justify-self: end;
      max-width: 420px;
      min-height: 38px;
      padding: 9px 12px;
      border: 1px solid var(--line);
      background: rgba(255, 253, 247, 0.72);
      color: var(--muted);
      font-size: 13px;
    }

    .layout {
      display: grid;
      grid-template-columns: minmax(0, 1.35fr) minmax(320px, 0.75fr);
      gap: 18px;
      align-items: start;
      padding-top: 18px;
    }

    .stack {
      display: grid;
      gap: 14px;
    }

    .panel {
      background: var(--surface);
      border: 1px solid var(--line);
      border-radius: 8px;
      box-shadow: var(--shadow);
      overflow: clip;
    }

    .panelHead {
      display: flex;
      justify-content: space-between;
      gap: 10px;
      align-items: center;
      padding: 12px 14px;
      border-bottom: 1px solid var(--line);
      background: rgba(247, 244, 234, 0.72);
    }

    .panelHead h2 {
      margin: 0;
      font-size: 15px;
      line-height: 1.2;
    }

    .panelHead span {
      color: var(--muted);
      font-size: 12px;
    }

    .body {
      padding: 14px;
    }

    .grid2 {
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 12px;
    }

    .field {
      display: grid;
      gap: 6px;
      min-width: 0;
    }

    label {
      color: var(--muted);
      font-size: 12px;
      line-height: 1.2;
    }

    input,
    textarea {
      width: 100%;
      border: 1px solid var(--line);
      border-radius: 6px;
      background: #fffefa;
      color: var(--ink);
    }

    input {
      height: 40px;
      padding: 8px 10px;
    }

    textarea {
      min-height: 132px;
      max-height: 44vh;
      padding: 10px;
      resize: vertical;
      line-height: 1.45;
      font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
      font-size: 12px;
    }

    .textareaTall {
      min-height: 190px;
    }

    .actions {
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      margin-top: 12px;
    }

    button {
      min-height: 38px;
      border: 1px solid var(--ink);
      border-radius: 6px;
      padding: 8px 12px;
      background: var(--ink);
      color: #fffdf7;
      cursor: pointer;
      font-weight: 700;
    }

    button.secondary {
      background: transparent;
      color: var(--ink);
    }

    button.positive {
      border-color: var(--green);
      background: var(--green);
    }

    button.blue {
      border-color: var(--blue);
      background: var(--blue);
    }

    button:disabled {
      cursor: wait;
      opacity: 0.6;
    }

    .previewRail {
      position: sticky;
      top: 12px;
      display: grid;
      gap: 14px;
    }

    .device {
      padding: 16px;
      border: 2px solid var(--ink);
      border-radius: 8px;
      background: #2b2a27;
      box-shadow: var(--shadow);
    }

    .screen {
      aspect-ratio: 4 / 3;
      border: 1px solid #000;
      background:
        repeating-linear-gradient(0deg, rgba(0, 0, 0, 0.035), rgba(0, 0, 0, 0.035) 1px, transparent 1px, transparent 4px),
        #f0efe6;
      color: #10100f;
      padding: 14px;
      overflow: hidden;
      display: grid;
      grid-template-rows: auto 1fr auto;
      gap: 9px;
    }

    .screenTop {
      display: flex;
      justify-content: space-between;
      gap: 8px;
      font-size: 11px;
      color: #444139;
      border-bottom: 1px solid #444139;
      padding-bottom: 5px;
    }

    .screenTitle {
      margin: 0;
      font-size: clamp(17px, 4vw, 24px);
      line-height: 1.05;
      word-break: break-word;
    }

    .screenList {
      display: grid;
      gap: 6px;
      min-height: 0;
      overflow: hidden;
      font-size: 12px;
      line-height: 1.3;
    }

    .screenItem {
      display: grid;
      grid-template-columns: 42px minmax(0, 1fr);
      gap: 6px;
      border-bottom: 1px dotted rgba(16, 16, 15, 0.35);
      padding-bottom: 4px;
      min-width: 0;
    }

    .screenItem strong,
    .screenItem span {
      overflow-wrap: anywhere;
    }

    .screenFoot {
      display: flex;
      justify-content: space-between;
      gap: 8px;
      font-size: 10px;
      color: #444139;
      border-top: 1px solid #444139;
      padding-top: 5px;
    }

    .hint {
      color: var(--muted);
      font-size: 12px;
      line-height: 1.45;
    }

    .error {
      color: var(--red);
    }

    @media (max-width: 860px) {
      .topbar,
      .layout,
      .grid2 {
        grid-template-columns: 1fr;
      }

      .status {
        justify-self: stretch;
        max-width: none;
      }

      .previewRail {
        position: static;
      }
    }

    @media (max-width: 520px) {
      .app {
        width: min(100% - 18px, 1180px);
        padding-top: 10px;
      }

      .panelHead,
      .body {
        padding-left: 10px;
        padding-right: 10px;
      }

      .actions button {
        flex: 1 1 132px;
      }
    }
  </style>
</head>
<body>
  <main class="app">
    <header class="topbar">
      <div class="brand">
        <div class="mark">GT</div>
        <div>
          <h1>GoTim Ink Meeting Console</h1>
          <p class="subtitle">本地会议控制台，修改后墨水屏继续读取同一套接口</p>
        </div>
      </div>
      <div id="status" class="status">正在读取会议数据...</div>
    </header>

    <section class="layout">
      <div class="stack">
        <section class="panel">
          <div class="panelHead">
            <h2>会议基本信息</h2>
            <span>保存到 /meeting/current</span>
          </div>
          <div class="body">
            <div class="grid2">
              <div class="field">
                <label for="meetingId">会议 ID</label>
                <input id="meetingId" autocomplete="off" placeholder="local-demo">
              </div>
              <div class="field">
                <label for="homeTitle">屏幕标题</label>
                <input id="homeTitle" autocomplete="off" placeholder="客户演示会议">
              </div>
              <div class="field">
                <label for="attendeeName">参会人</label>
                <input id="attendeeName" autocomplete="off" placeholder="客户嘉宾">
              </div>
              <div class="field">
                <label for="attendeeRole">角色</label>
                <input id="attendeeRole" autocomplete="off" placeholder="Demo">
              </div>
              <div class="field">
                <label for="materialsUrl">资料二维码链接</label>
                <input id="materialsUrl" inputmode="url" autocomplete="off" placeholder="http://电脑IP:8787/files/materials.txt">
              </div>
              <div class="field">
                <label for="interactionUrl">提问链接</label>
                <input id="interactionUrl" inputmode="url" autocomplete="off" placeholder="http://电脑IP:8787/files/questions.txt">
              </div>
              <div class="field">
                <label for="reminderUrl">提醒下载链接</label>
                <input id="reminderUrl" inputmode="url" autocomplete="off" placeholder="http://电脑IP:8787/files/reminders.txt">
              </div>
              <div class="field">
                <label for="agendaIndex">当前议程序号</label>
                <input id="agendaIndex" inputmode="numeric" autocomplete="off" placeholder="0">
              </div>
            </div>
            <div class="actions">
              <button class="secondary" type="button" onclick="loadMeeting()">重新读取</button>
              <button class="positive" type="button" onclick="saveMeeting()">保存基本信息</button>
              <button class="blue" type="button" onclick="saveFleetPush()">一键推送全部设备</button>
            </div>
          </div>
        </section>

        <section class="panel">
          <div class="panelHead">
            <h2>议程</h2>
            <span>JSON 数组，保存到 /meeting/agenda</span>
          </div>
          <div class="body">
            <textarea id="agendaEditor" class="textareaTall" spellcheck="false"></textarea>
            <div class="actions">
              <button class="positive" type="button" onclick="saveAgenda()">保存议程</button>
              <button class="secondary" type="button" onclick="formatJson('agendaEditor')">格式化</button>
            </div>
          </div>
        </section>

        <section class="panel">
          <div class="panelHead">
            <h2>个人提醒</h2>
            <span>JSON 数组，保存到 /meeting/reminders</span>
          </div>
          <div class="body">
            <textarea id="reminderEditor" spellcheck="false"></textarea>
            <div class="actions">
              <button class="positive" type="button" onclick="saveReminders()">保存提醒</button>
              <button class="secondary" type="button" onclick="formatJson('reminderEditor')">格式化</button>
            </div>
          </div>
        </section>

        <section class="panel">
          <div class="panelHead">
            <h2>实时纪要模拟</h2>
            <span>按“说话人：内容”逐行输入</span>
          </div>
          <div class="body">
            <div class="field">
              <label for="speakerLabel">当前发言人</label>
              <input id="speakerLabel" autocomplete="off" value="未知发言人" placeholder="输入姓名或角色">
            </div>
            <div class="actions" style="margin-bottom: 10px;">
              <button id="startRecording" class="positive" type="button" onclick="startRecordingSession()">开始录音</button>
              <button id="pauseRecording" class="secondary" type="button" onclick="pauseRecordingSession()" disabled>暂停</button>
              <button id="resumeRecording" class="secondary" type="button" onclick="resumeRecordingSession()" disabled>继续</button>
              <button id="stopRecording" class="blue" type="button" onclick="stopRecordingSession()" disabled>结束并总结</button>
            </div>
            <div id="recordingState" class="hint">等待录音；拒绝麦克风权限时仍可手工输入纪要。</div>
            <textarea id="transcriptEditor" placeholder="Jasper：客户希望只带 iPhone 和墨水屏完成演示&#10;客户：二维码要能下载会议资料"></textarea>
            <div class="field" style="margin-top: 10px;">
              <label for="keywords">关键词，逗号分隔</label>
              <input id="keywords" autocomplete="off" placeholder="iPhone,二维码,会议摘要">
            </div>
            <div class="actions">
              <button class="blue" type="button" onclick="sendTranscript()">发送纪要并生成摘要</button>
            </div>
          </div>
        </section>
      </div>

      <aside class="previewRail">
        <section class="device" aria-label="墨水屏预览">
          <div class="screen">
            <div class="screenTop">
              <span id="previewMeetingId">local-demo</span>
              <span id="previewAttendee">客户嘉宾</span>
            </div>
            <div>
              <h2 id="previewTitle" class="screenTitle">客户演示会议</h2>
              <div id="previewAgenda" class="screenList"></div>
            </div>
            <div class="screenFoot">
              <span id="previewMaterial">资料二维码</span>
              <span id="previewReminder">提醒</span>
            </div>
          </div>
        </section>
        <section class="panel">
          <div class="panelHead">
            <h2>操作口径</h2>
            <span>Demo</span>
          </div>
          <div class="body">
            <p class="hint">手机和电脑在同一个网络时，手机打开这个页面即可改议程、材料链接和提醒。保存后设备端下一次拉取 `/meeting/current` 会看到新内容。</p>
          </div>
        </section>
      </aside>
    </section>
  </main>

  <script>
    let currentMeeting = {};
    const statusEl = document.getElementById("status");
    let mediaRecorder = null;
    let mediaStream = null;
    let recordingSessionId = null;
    let recordingSequence = 0;
    let eventSource = null;

    function setRecordingButtons(state) {
      document.getElementById("startRecording").disabled = state !== "idle";
      document.getElementById("pauseRecording").disabled = state !== "recording";
      document.getElementById("resumeRecording").disabled = state !== "paused";
      document.getElementById("stopRecording").disabled = !["recording", "paused"].includes(state);
      document.getElementById("recordingState").textContent = {idle: "等待录音", recording: "正在录音并实时同步", paused: "录音已暂停", finalizing: "正在生成最终总结"}[state] || state;
    }

    function blobToBase64(blob) {
      return new Promise((resolve, reject) => {
        const reader = new FileReader();
        reader.onload = () => resolve(String(reader.result).split(",")[1] || "");
        reader.onerror = reject;
        reader.readAsDataURL(blob);
      });
    }

    async function uploadChunk(blob) {
      if (!recordingSessionId || blob.size === 0) return;
      const sequence = recordingSequence++;
      const audio_b64 = await blobToBase64(blob);
      await fetchJson(`/api/recordings/${recordingSessionId}/chunks`, {
        method: "POST",
        body: JSON.stringify({sequence, speaker: document.getElementById("speakerLabel").value.trim() || "未知发言人", mime_type: mediaRecorder.mimeType, audio_b64})
      });
    }

    async function startRecordingSession() {
      try {
        mediaStream = await navigator.mediaDevices.getUserMedia({audio: true});
        mediaRecorder = new MediaRecorder(mediaStream);
        const created = await fetchJson("/api/recordings", {method: "POST", body: JSON.stringify({meeting_id: currentMeeting.meeting_id || "meeting", mime_type: mediaRecorder.mimeType})});
        recordingSessionId = created.session_id;
        recordingSequence = 0;
        mediaRecorder.ondataavailable = (event) => uploadChunk(event.data).catch((error) => setStatus(error.message, true));
        mediaRecorder.start(2000);
        setRecordingButtons("recording");
      } catch (error) {
        setStatus(`麦克风权限或录音启动失败：${error.message}。可继续手工输入纪要。`, true);
        setRecordingButtons("idle");
      }
    }

    async function pauseRecordingSession() {
      mediaRecorder.pause();
      await fetchJson(`/api/recordings/${recordingSessionId}/pause`, {method: "POST", body: "{}"});
      setRecordingButtons("paused");
    }

    async function resumeRecordingSession() {
      mediaRecorder.resume();
      await fetchJson(`/api/recordings/${recordingSessionId}/resume`, {method: "POST", body: "{}"});
      setRecordingButtons("recording");
    }

    async function stopRecordingSession() {
      setRecordingButtons("finalizing");
      mediaRecorder.stop();
      mediaStream.getTracks().forEach((track) => track.stop());
      await fetchJson(`/api/recordings/${recordingSessionId}/stop`, {method: "POST", body: "{}"});
      recordingSessionId = null;
      await loadMeeting();
      setRecordingButtons("idle");
    }

    function connectEvents() {
      if (eventSource) eventSource.close();
      eventSource = new EventSource("/api/events");
      ["transcript", "summary", "status"].forEach((name) => eventSource.addEventListener(name, () => loadMeeting()));
      eventSource.onerror = () => setStatus("实时连接中断，正在自动重连", true);
    }

    function setStatus(message, isError = false) {
      statusEl.textContent = message;
      statusEl.classList.toggle("error", isError);
    }

    async function fetchJson(url, options = {}) {
      const response = await fetch(url, {
        headers: {"Content-Type": "application/json", ...(options.headers || {})},
        cache: "no-store",
        ...options
      });
      const payload = await response.json();
      if (!response.ok || payload.ok === false) {
        throw new Error(payload.error || `HTTP ${response.status}`);
      }
      return payload;
    }

    function pretty(value) {
      return JSON.stringify(value || [], null, 2);
    }

    function parseJsonArray(id, label) {
      const value = JSON.parse(document.getElementById(id).value || "[]");
      if (!Array.isArray(value)) {
        throw new Error(`${label}必须是 JSON 数组`);
      }
      return value;
    }

    function formatJson(id) {
      try {
        const element = document.getElementById(id);
        element.value = pretty(JSON.parse(element.value || "[]"));
        setStatus("JSON 已格式化");
      } catch (error) {
        setStatus(error.message, true);
      }
    }

    function fillForm(meeting) {
      currentMeeting = meeting || {};
      document.getElementById("meetingId").value = currentMeeting.meeting_id || "";
      document.getElementById("homeTitle").value = currentMeeting.home?.title || "";
      document.getElementById("attendeeName").value = currentMeeting.attendee?.name || "";
      document.getElementById("attendeeRole").value = currentMeeting.attendee?.role || "";
      document.getElementById("materialsUrl").value = currentMeeting.materials?.url || "";
      document.getElementById("interactionUrl").value = currentMeeting.interaction?.url || "";
      document.getElementById("reminderUrl").value = currentMeeting.reminder?.url || "";
      document.getElementById("agendaIndex").value = Number.isInteger(currentMeeting.current_agenda_index) ? currentMeeting.current_agenda_index : 0;
      document.getElementById("agendaEditor").value = pretty(currentMeeting.agenda);
      document.getElementById("reminderEditor").value = pretty(currentMeeting.reminder?.items);
      document.getElementById("keywords").value = (currentMeeting.summary?.keywords || []).join(",");
      updatePreview();
    }

    function readBaseForm() {
      currentMeeting.home = currentMeeting.home || {};
      currentMeeting.attendee = currentMeeting.attendee || {};
      currentMeeting.materials = currentMeeting.materials || {label: "会议资料"};
      currentMeeting.interaction = currentMeeting.interaction || {label: "提交问题"};
      currentMeeting.reminder = currentMeeting.reminder || {items: []};
      currentMeeting.meeting_id = document.getElementById("meetingId").value.trim() || "local-demo";
      currentMeeting.home.title = document.getElementById("homeTitle").value.trim() || "客户演示会议";
      currentMeeting.attendee.name = document.getElementById("attendeeName").value.trim() || "客户嘉宾";
      currentMeeting.attendee.role = document.getElementById("attendeeRole").value.trim() || "Demo";
      currentMeeting.materials.url = document.getElementById("materialsUrl").value.trim();
      currentMeeting.interaction.url = document.getElementById("interactionUrl").value.trim();
      currentMeeting.reminder.url = document.getElementById("reminderUrl").value.trim();
      currentMeeting.current_agenda_index = Number.parseInt(document.getElementById("agendaIndex").value || "0", 10) || 0;
      updatePreview();
      return currentMeeting;
    }

    function updatePreview() {
      const meeting = readPreviewMeeting();
      document.getElementById("previewMeetingId").textContent = meeting.meeting_id || "local-demo";
      document.getElementById("previewAttendee").textContent = meeting.attendee?.name || "客户嘉宾";
      document.getElementById("previewTitle").textContent = meeting.home?.title || "客户演示会议";
      document.getElementById("previewMaterial").textContent = meeting.materials?.url ? "资料可扫码" : "未配置资料";
      document.getElementById("previewReminder").textContent = `${(meeting.reminder?.items || []).length} 条提醒`;
      const agenda = (meeting.agenda || []).slice(0, 4);
      document.getElementById("previewAgenda").innerHTML = agenda.map((item, index) => {
        const time = escapeHtml(item.time || `#${index + 1}`);
        const title = escapeHtml(item.title || item.note || "未命名议程");
        return `<div class="screenItem"><strong>${time}</strong><span>${title}</span></div>`;
      }).join("") || '<div class="screenItem"><strong>--</strong><span>暂无议程</span></div>';
    }

    function readPreviewMeeting() {
      const meeting = structuredClone(currentMeeting || {});
      meeting.home = {...(meeting.home || {}), title: document.getElementById("homeTitle").value.trim()};
      meeting.attendee = {...(meeting.attendee || {}), name: document.getElementById("attendeeName").value.trim()};
      meeting.materials = {...(meeting.materials || {}), url: document.getElementById("materialsUrl").value.trim()};
      meeting.meeting_id = document.getElementById("meetingId").value.trim();
      try {
        meeting.agenda = JSON.parse(document.getElementById("agendaEditor").value || "[]");
      } catch {
        meeting.agenda = [];
      }
      try {
        const items = JSON.parse(document.getElementById("reminderEditor").value || "[]");
        meeting.reminder = {...(meeting.reminder || {}), items: Array.isArray(items) ? items : []};
      } catch {
        meeting.reminder = {...(meeting.reminder || {}), items: []};
      }
      return meeting;
    }

    function escapeHtml(value) {
      return String(value).replace(/[&<>"']/g, (char) => ({
        "&": "&amp;",
        "<": "&lt;",
        ">": "&gt;",
        '"': "&quot;",
        "'": "&#39;"
      })[char]);
    }

    async function loadMeeting() {
      try {
        setStatus("正在读取会议数据...");
        const payload = await fetchJson("/meeting/current");
        fillForm(payload.data);
        setStatus(`已读取：${payload.data.meeting_id || "local-demo"}`);
      } catch (error) {
        setStatus(error.message, true);
      }
    }

    async function saveMeeting() {
      try {
        const meeting = readBaseForm();
        const payload = await fetchJson("/meeting/current", {
          method: "POST",
          body: JSON.stringify({data: meeting})
        });
        fillForm(payload.data);
        setStatus("基本信息已保存");
      } catch (error) {
        setStatus(error.message, true);
      }
    }

    async function saveFleetPush() {
      try {
        const meeting = readBaseForm();
        meeting.live = meeting.live || {};
        meeting.live.remote_update = "母机同步全部设备";
        const payload = await fetchJson("/fleet/push", {
          method: "POST",
          body: JSON.stringify({data: meeting})
        });
        fillForm(payload.data);
        setStatus("已一键推送全部设备");
      } catch (error) {
        setStatus(error.message, true);
      }
    }

    async function saveAgenda() {
      try {
        readBaseForm();
        const agenda = parseJsonArray("agendaEditor", "议程");
        const current_agenda_index = Number.parseInt(document.getElementById("agendaIndex").value || "0", 10) || 0;
        const payload = await fetchJson("/meeting/agenda", {
          method: "POST",
          body: JSON.stringify({agenda, current_agenda_index})
        });
        fillForm(payload.data);
        setStatus("议程已保存");
      } catch (error) {
        setStatus(error.message, true);
      }
    }

    async function saveReminders() {
      try {
        readBaseForm();
        const items = parseJsonArray("reminderEditor", "提醒");
        const url = document.getElementById("reminderUrl").value.trim();
        const payload = await fetchJson("/meeting/reminders", {
          method: "POST",
          body: JSON.stringify({items, url})
        });
        fillForm(payload.data);
        setStatus("提醒已保存");
      } catch (error) {
        setStatus(error.message, true);
      }
    }

    function parseTranscript() {
      return document.getElementById("transcriptEditor").value
        .split(/\n+/)
        .map((line) => line.trim())
        .filter(Boolean)
        .map((line) => {
          const match = line.match(/^([^:：]{1,18})[:：](.+)$/);
          return match
            ? {speaker: match[1].trim(), text: match[2].trim()}
            : {speaker: "发言", text: line};
        });
    }

    async function sendTranscript() {
      try {
        const segments = parseTranscript();
        if (segments.length === 0) {
          throw new Error("请先输入纪要内容");
        }
        const keywords = document.getElementById("keywords").value
          .split(/[,，]/)
          .map((item) => item.trim())
          .filter(Boolean);
        const payload = await fetchJson("/meeting/transcript", {
          method: "POST",
          body: JSON.stringify({segments, keywords})
        });
        fillForm(payload.data);
        setStatus("纪要已发送，摘要已更新");
      } catch (error) {
        setStatus(error.message, true);
      }
    }

    ["meetingId", "homeTitle", "attendeeName", "materialsUrl", "agendaEditor", "reminderEditor"].forEach((id) => {
      document.addEventListener("input", (event) => {
        if (event.target && event.target.id === id) {
          updatePreview();
        }
      });
    });

    setRecordingButtons("idle");
    connectEvents();
    loadMeeting();
  </script>
</body>
</html>
"""


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def default_meeting_payload() -> dict:
    if SEED_DATA.exists():
        return read_json(SEED_DATA)
    return {
        "meeting_id": "local-demo",
        "updated_at": now_iso(),
        "home": {
            "title": "极趣实验室 Note",
            "date_label": "",
            "month": "",
            "day": "",
            "weekday": "",
        },
        "device_status": {"network": "本地", "mode": "Demo", "nfc": "Ready", "battery": "--"},
        "attendee": {"id": "guest-001", "name": "客户嘉宾", "role": "Demo"},
        "badge": {"label": "会后身份 Badge", "footer": "会后可带走设备作为身份牌"},
        "live": {
            "speaker": "主持人",
            "topic": "会议开场",
            "status": "等待发言",
            "remote_update": "母机同步 0 台设备",
        },
        "current_agenda_index": 0,
        "agenda": [],
        "materials": {"label": "会议资料", "url": "http://127.0.0.1:8787/files/materials.txt"},
        "interaction": {"label": "提交问题", "url": "http://127.0.0.1:8787/files/questions.txt"},
        "summary": {
            "title": "实时摘要",
            "bullets": [],
            "keywords": [],
            "metrics": [
                {"label": "核心数据", "value": "--", "delta": "待更新"},
                {"label": "发言人数", "value": "--", "delta": "实时"},
                {"label": "待办", "value": "--", "delta": "会后"},
            ],
        },
        "reminder": {"url": "http://127.0.0.1:8787/files/reminders.txt", "items": []},
        "desktop_tasks": [],
        "health_reminders": [
            {"time": "10:50", "title": "起身活动 3 分钟"},
            {"time": "15:00", "title": "喝水提醒"},
        ],
    }


def now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).astimezone().isoformat(timespec="seconds")


def unwrap_meeting_payload(payload: dict) -> dict:
    if isinstance(payload.get("data"), dict):
        return payload["data"]
    return payload


def trim_text(value: object, limit: int = 48) -> str:
    text = str(value or "").strip()
    if len(text) <= limit:
        return text
    return text[: limit - 1] + "..."


def summary_from_segments(segments: list[dict], keywords: list[str] | None = None) -> dict:
    bullets: list[str] = []
    for segment in segments[-5:]:
        speaker = trim_text(segment.get("speaker") or "发言", 12)
        text = trim_text(segment.get("text"), 42)
        if text:
            bullets.append(f"{speaker}：{text}")
    return {
        "title": "实时摘要",
        "bullets": bullets,
        "keywords": keywords or [],
    }


class MeetingHandler(BaseHTTPRequestHandler):
    data_path: Path = DEFAULT_DATA
    file_root: Path = DEFAULT_FILES
    note_store_path: Path = DEFAULT_NOTES
    realtime_manager = None
    note_store = None

    @classmethod
    def reset_realtime_runtime(cls) -> None:
        cls.realtime_manager = None

    @classmethod
    def get_realtime_manager(cls) -> RecordingManager:
        manager = cls.realtime_manager
        if manager is None or manager.store.path != cls.data_path:
            manager = RecordingManager(VersionedMeetingStore(cls.data_path))
            cls.realtime_manager = manager
        return manager

    @classmethod
    def get_note_store(cls) -> VersionedNoteStore:
        store = cls.note_store
        if store is None or store.path != cls.note_store_path:
            store = VersionedNoteStore(cls.note_store_path)
            cls.note_store = store
        return store

    def send_json(self, status: int, payload: dict) -> None:
        raw = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, PATCH, DELETE, PUT, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def send_html(self, status: int, html: str) -> None:
        raw = html.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def send_file(self, path: Path) -> None:
        raw = path.read_bytes()
        content_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Cache-Control", "no-store")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def read_body_json(self) -> dict | None:
        length = int(self.headers.get("Content-Length", "0"))
        try:
            payload = json.loads(self.rfile.read(length).decode("utf-8"))
        except json.JSONDecodeError as exc:
            self.send_json(400, {"ok": False, "error": f"invalid_json: {exc}"})
            return None
        if not isinstance(payload, dict):
            self.send_json(400, {"ok": False, "error": "payload_must_be_object"})
            return None
        return payload

    def current_meeting(self) -> dict:
        if not self.data_path.exists():
            write_json(self.data_path, default_meeting_payload())
        return read_json(self.data_path)

    def save_current_meeting(self, payload: dict) -> dict:
        def replace(candidate: dict) -> None:
            candidate.clear()
            candidate.update(payload)

        return self.get_realtime_manager().store.mutate(replace)

    @staticmethod
    def note_id_from_path(path: str) -> str | None:
        prefix = "/notes/"
        if not path.startswith(prefix):
            return None
        encoded_id = path.removeprefix(prefix)
        if not encoded_id or "/" in encoded_id:
            return None
        return unquote(encoded_id)

    def send_note_error(self, error: Exception) -> None:
        if isinstance(error, VersionConflictError):
            self.send_json(409, {"ok": False, "error": str(error), "data": error.snapshot})
        elif isinstance(error, KeyError):
            self.send_json(404, {"ok": False, "error": "note_not_found"})
        else:
            self.send_json(400, {"ok": False, "error": str(error)})

    def handle_note_mutation(self, status: int, action: str, note_id: str | None = None) -> None:
        payload = self.read_body_json()
        if payload is None:
            return
        base_version = payload.pop("base_version", None)
        store = self.get_note_store()
        previous_version = int(store.read().get("version", 0))
        try:
            if action == "create":
                snapshot = store.create(payload, base_version)
            elif action == "patch":
                snapshot = store.patch(note_id or "", payload, base_version)
            elif action == "delete":
                snapshot = store.delete(note_id or "", base_version)
            else:
                snapshot = store.reorder(payload.get("ids"), base_version)
        except (NoteValidationError, VersionConflictError, KeyError) as error:
            self.send_note_error(error)
            return

        version = int(snapshot.get("version", 0))
        if version != previous_version:
            self.get_realtime_manager().broker.publish("notes", version, snapshot)

        response = {"ok": True, "version": version, "data": snapshot}
        if action == "create":
            response["note"] = snapshot["notes"][-1]
        elif action == "patch":
            response["note"] = next(note for note in snapshot["notes"] if note["id"] == note_id)
        self.send_json(status, response)

    def do_OPTIONS(self) -> None:
        self.send_json(200, {"ok": True})

    def do_GET(self) -> None:
        path = urlparse(self.path).path
        if path in ("/", "/editor"):
            self.send_html(200, EDITOR_HTML)
            return
        if path == "/health":
            self.send_json(200, {"ok": True})
            return
        if path == "/notes":
            self.send_json(200, self.get_note_store().read())
            return
        if path == "/notes/version":
            state = self.get_note_store().read()
            self.send_json(200, {"version": int(state.get("version", 0)), "updated_at": state.get("updated_at")})
            return
        if path == "/meeting/current":
            self.send_json(200, {"ok": True, "data": self.current_meeting()})
            return
        if path == "/meeting/version":
            state = self.get_realtime_manager().store.read()
            self.send_json(200, {"ok": True, "version": int(state.get("version", 0)), "updated_at": state.get("updated_at", ""), "update_priority": state.get("update_priority", "normal")})
            return
        if path == "/api/events":
            last_id = int(self.headers.get("Last-Event-ID", "0") or 0)
            events = self.get_realtime_manager().broker.events_after(last_id)
            raw = "".join(
                "id: {}\nevent: {}\ndata: {}\n\n".format(
                    item["id"], item["event"], json.dumps(item["data"], ensure_ascii=False)
                )
                for item in events
            ).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream; charset=utf-8")
            self.send_header("Cache-Control", "no-cache")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)
            return
        if path in ("/meeting/export.json", "/meeting/export.txt"):
            state = self.get_realtime_manager().store.read()
            if path.endswith(".json"):
                raw = json.dumps(state, ensure_ascii=False, indent=2).encode("utf-8")
                content_type = "application/json; charset=utf-8"
            else:
                transcript = state.get("transcript", {}).get("segments", [])
                summary = state.get("summary", {})
                lines = [summary.get("title", "会议总结"), ""] + list(summary.get("bullets") or []) + ["", "转写"]
                lines += ["{}：{}".format(item.get("speaker", "未知发言人"), item.get("text", "")) for item in transcript]
                raw = ("\n".join(lines) + "\n").encode("utf-8")
                content_type = "text/plain; charset=utf-8"
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)
            return
        if path.startswith("/files/"):
            root = self.file_root.resolve()
            rel = unquote(path.removeprefix("/files/"))
            candidate = (root / rel).resolve()
            try:
                candidate.relative_to(root)
            except ValueError:
                self.send_json(404, {"ok": False, "error": "not_found"})
                return
            if not candidate.is_file():
                self.send_json(404, {"ok": False, "error": "not_found"})
                return
            self.send_file(candidate)
            return
        self.send_json(404, {"ok": False, "error": "not_found"})

    def do_POST(self) -> None:
        path = urlparse(self.path).path
        if path == "/notes":
            self.handle_note_mutation(201, "create")
            return
        manager = self.get_realtime_manager()
        if path == "/api/recordings":
            payload = self.read_body_json()
            if payload is None:
                return
            session, state = manager.create(str(payload.get("meeting_id") or "meeting"), str(payload.get("mime_type") or "audio/webm"))
            self.send_json(201, {"ok": True, "session_id": session.session_id, "version": state.get("version", 0), "status": session.status})
            return
        if path.startswith("/api/recordings/"):
            parts = path.strip("/").split("/")
            if len(parts) != 4:
                self.send_json(404, {"ok": False, "error": "not_found"})
                return
            session_id, action = parts[2], parts[3]
            payload = self.read_body_json()
            if payload is None:
                return
            try:
                if action == "chunks":
                    result = manager.accept_chunk(session_id, int(payload.get("sequence", -1)), b"", payload)
                    self.send_json(200, {"ok": True, **result})
                elif action == "pause":
                    state = manager.pause(session_id)
                    self.send_json(200, {"ok": True, "status": "paused", "version": state.get("version", 0)})
                elif action == "resume":
                    state = manager.resume(session_id)
                    self.send_json(200, {"ok": True, "status": "recording", "version": state.get("version", 0)})
                elif action == "stop":
                    state = manager.stop(session_id)
                    self.send_json(200, {"ok": True, "status": "complete", "version": state.get("version", 0), "data": state})
                else:
                    self.send_json(404, {"ok": False, "error": "not_found"})
            except SequenceGapError as error:
                self.send_json(409, {"ok": False, "error": "sequence_gap", "expected_sequence": error.expected})
            except KeyError:
                self.send_json(404, {"ok": False, "error": "session_not_found"})
            except (TypeError, ValueError) as error:
                self.send_json(409, {"ok": False, "error": str(error)})
            return
        if path == "/meeting/current":
            payload = self.read_body_json()
            if payload is None:
                return
            meeting = unwrap_meeting_payload(payload)
            meeting = self.save_current_meeting(meeting)
            self.send_json(200, {"ok": True, "data": meeting})
            return

        if path == "/fleet/push":
            payload = self.read_body_json()
            if payload is None:
                return
            meeting = unwrap_meeting_payload(payload)
            live = meeting.setdefault("live", {})
            live["remote_update"] = live.get("remote_update") or "母机同步全部设备"
            meeting = self.save_current_meeting(meeting)
            self.send_json(200, {"ok": True, "data": meeting})
            return

        if path == "/meeting/agenda":
            payload = self.read_body_json()
            if payload is None:
                return
            agenda = payload.get("agenda")
            if not isinstance(agenda, list):
                self.send_json(400, {"ok": False, "error": "agenda_must_be_array"})
                return
            meeting = self.current_meeting()
            meeting["agenda"] = agenda
            if isinstance(payload.get("current_agenda_index"), int):
                meeting["current_agenda_index"] = payload["current_agenda_index"]
            meeting = self.save_current_meeting(meeting)
            self.send_json(200, {"ok": True, "data": meeting})
            return

        if path == "/meeting/reminders":
            payload = self.read_body_json()
            if payload is None:
                return
            reminder_payload = payload.get("reminder") if isinstance(payload.get("reminder"), dict) else payload
            items = reminder_payload.get("items")
            if not isinstance(items, list):
                self.send_json(400, {"ok": False, "error": "items_must_be_array"})
                return
            meeting = self.current_meeting()
            reminder = meeting.setdefault("reminder", {})
            reminder["items"] = items
            if isinstance(reminder_payload.get("url"), str):
                reminder["url"] = reminder_payload["url"]
            meeting["active_reminder_index"] = -1
            meeting = self.save_current_meeting(meeting)
            self.send_json(200, {"ok": True, "data": meeting})
            return

        if path == "/meeting/transcript":
            payload = self.read_body_json()
            if payload is None:
                return
            segments = payload.get("segments")
            if segments is None and isinstance(payload.get("text"), str):
                segments = [{"speaker": payload.get("speaker", "发言"), "text": payload["text"]}]
            if not isinstance(segments, list) or not all(isinstance(item, dict) for item in segments):
                self.send_json(400, {"ok": False, "error": "segments_must_be_array"})
                return
            normalized_segments = [
                {
                    "speaker": str(item.get("speaker") or "发言").strip(),
                    "text": str(item.get("text") or "").strip(),
                    "time": str(item.get("time") or now_iso()),
                }
                for item in segments
                if str(item.get("text") or "").strip()
            ]
            meeting = self.current_meeting()
            transcript = meeting.setdefault("transcript", {"segments": []})
            transcript["segments"] = (transcript.get("segments", []) + normalized_segments)[-80:]
            if isinstance(payload.get("summary"), dict):
                meeting["summary"] = payload["summary"]
            else:
                keywords = payload.get("keywords")
                meeting["summary"] = summary_from_segments(
                    transcript["segments"],
                    keywords if isinstance(keywords, list) else meeting.get("summary", {}).get("keywords", []),
                )
            meeting = self.save_current_meeting(meeting)
            self.send_json(200, {"ok": True, "data": meeting})
            return

        if path not in ("/meeting/current", "/fleet/push"):
            self.send_json(404, {"ok": False, "error": "not_found"})
            return

    def do_PATCH(self) -> None:
        path = urlparse(self.path).path
        note_id = self.note_id_from_path(path)
        if note_id is not None:
            self.handle_note_mutation(200, "patch", note_id)
            return
        if not path.startswith("/api/transcript/"):
            self.send_json(404, {"ok": False, "error": "not_found"})
            return
        payload = self.read_body_json()
        if payload is None:
            return
        segment_id = path.rsplit("/", 1)[-1]
        try:
            segment, state = self.get_realtime_manager().correct_segment(segment_id, payload)
        except KeyError:
            self.send_json(404, {"ok": False, "error": "segment_not_found"})
            return
        self.send_json(200, {"ok": True, "segment": segment, "version": state.get("version", 0)})

    def do_DELETE(self) -> None:
        path = urlparse(self.path).path
        note_id = self.note_id_from_path(path)
        if note_id is None:
            self.send_json(404, {"ok": False, "error": "not_found"})
            return
        self.handle_note_mutation(200, "delete", note_id)

    def do_PUT(self) -> None:
        path = urlparse(self.path).path
        if path != "/notes/reorder":
            self.send_json(404, {"ok": False, "error": "not_found"})
            return
        self.handle_note_mutation(200, "reorder")

    def log_message(self, fmt: str, *args) -> None:
        print(f"{self.address_string()} - {fmt % args}")


def create_server(host: str, port: int) -> ThreadingHTTPServer:
    try:
        return ThreadingHTTPServer((host, port), MeetingHandler)
    except OSError as error:
        raise SystemExit(
            f"Cannot start meeting server on {host}:{port}: {error}. "
            "Stop the occupying process or choose another --port."
        ) from None


def main() -> int:
    parser = argparse.ArgumentParser(description="Local meeting assistant JSON server.")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8787)
    parser.add_argument("--data", type=Path, default=DEFAULT_DATA)
    parser.add_argument("--files", type=Path, default=DEFAULT_FILES)
    args = parser.parse_args()

    if not args.data.exists():
        write_json(args.data, default_meeting_payload())
    args.files.mkdir(parents=True, exist_ok=True)
    MeetingHandler.data_path = args.data
    MeetingHandler.file_root = args.files
    server = create_server(args.host, args.port)
    print(f"meeting server: http://{args.host}:{args.port}")
    print(f"data file: {args.data}")
    print(f"files: {args.files}")
    server.serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
