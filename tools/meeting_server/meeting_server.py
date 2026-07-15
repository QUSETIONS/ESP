#!/usr/bin/env python3
from __future__ import annotations

import argparse
import base64
import binascii
import datetime as dt
import json
import mimetypes
import threading
import time
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlparse

try:
    from .asr_providers import build_asr_provider
    from .zectrix_cloud import ZectrixCloudError, build_meeting_pages, build_zectrix_client
    from .note_store import NoteValidationError, VersionConflictError, VersionedNoteStore
    from .realtime_summary import (
        AsrProviderError,
        RecordingManager,
        SequenceGapError,
        VersionedMeetingStore,
        format_sse,
        MAX_AUDIO_CHUNK_BYTES,
)
except ImportError:
    from asr_providers import build_asr_provider
    from zectrix_cloud import ZectrixCloudError, build_meeting_pages, build_zectrix_client
    from note_store import NoteValidationError, VersionConflictError, VersionedNoteStore
    from realtime_summary import (
        AsrProviderError,
        RecordingManager,
        SequenceGapError,
        VersionedMeetingStore,
        format_sse,
        MAX_AUDIO_CHUNK_BYTES,
)


ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = ROOT.parents[1]
SEED_DATA = PROJECT_ROOT / "tools" / "meeting_data" / "meeting_current.json"
DEFAULT_DATA = ROOT / "state" / "meeting_current.json"
DEFAULT_FILES = ROOT / "files"
DEFAULT_NOTES = ROOT / "state" / "notes.json"
MAX_JSON_BODY_BYTES = 2 * 1024 * 1024

EDITOR_HTML = r"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>GoTim Ink Meeting Console · 会议控制台</title>
  <style>
    :root {
      --paper: #eef2f4;
      --surface: #ffffff;
      --ink: #202a31;
      --muted: #65737b;
      --line: #ced8dd;
      --green: #14745f;
      --red: #b44a3a;
      --blue: #27658e;
      --amber: #a56a18;
      --shadow: 0 8px 22px rgba(31, 48, 58, 0.08);
    }

    * {
      box-sizing: border-box;
    }

    body {
      margin: 0;
      background: var(--paper);
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
      align-items: center;
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
      font-size: 30px;
      line-height: 1.05;
      letter-spacing: 0;
    }

    .subtitle {
      margin: 5px 0 0;
      color: var(--muted);
      font-size: 13px;
    }

    .status {
      display: inline-flex;
      align-items: center;
      gap: 8px;
      justify-self: end;
      max-width: 420px;
      min-height: 38px;
      padding: 9px 12px;
      border: 1px solid var(--line);
      background: rgba(255, 253, 247, 0.72);
      color: var(--muted);
      font-size: 13px;
    }

    .status::before {
      content: "";
      width: 8px;
      height: 8px;
      border-radius: 50%;
      background: var(--green);
      box-shadow: 0 0 0 3px rgba(20, 116, 95, 0.12);
      flex: 0 0 auto;
    }

    .controlPlane {
      display: grid;
      grid-template-columns: minmax(180px, 0.85fr) minmax(0, 2.6fr) 36px;
      gap: 0;
      align-items: stretch;
      min-height: 76px;
      margin-top: 12px;
      border: 1px solid var(--line);
      border-left: 4px solid var(--blue);
      background: var(--surface);
      box-shadow: 0 4px 12px rgba(31, 48, 58, 0.05);
    }

    .controlLead {
      display: grid;
      align-content: center;
      gap: 3px;
      min-width: 0;
      padding: 11px 14px;
    }

    .controlEyebrow,
    .controlLead span,
    .controlMetric dt {
      color: var(--muted);
      font-size: 10px;
      line-height: 1.2;
    }

    .controlEyebrow {
      color: var(--blue);
      font-weight: 800;
    }

    .controlLead strong,
    .controlMetric dd {
      overflow-wrap: anywhere;
    }

    .controlLead strong {
      font-size: 15px;
      line-height: 1.2;
    }

    .controlMetrics {
      display: grid;
      grid-template-columns: repeat(4, minmax(0, 1fr));
      margin: 0;
      min-width: 0;
    }

    .controlMetric {
      display: grid;
      align-content: center;
      gap: 6px;
      min-width: 0;
      margin: 0;
      padding: 10px 12px;
      border-left: 1px solid var(--line);
    }

    .controlMetric dd {
      margin: 0;
      font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
      font-size: 12px;
      font-weight: 800;
      line-height: 1.3;
    }

    .controlRefresh {
      align-self: center;
      width: 30px;
      min-height: 30px;
      margin: 0 6px 0 0;
      padding: 0;
      border-color: var(--line);
      background: transparent;
      color: var(--ink);
      font-size: 18px;
      line-height: 1;
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
      border-radius: 6px;
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
      min-width: 0;
      max-width: 58%;
      overflow: hidden;
      text-align: right;
      text-overflow: ellipsis;
      white-space: nowrap;
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

    .realtimeOutput {
      display: grid;
      gap: 10px;
      margin-top: 12px;
      padding: 12px;
      border: 1px solid var(--line);
      background: #fbfaf4;
    }

    .realtimeHeader,
    .realtimeRow {
      display: flex;
      justify-content: space-between;
      gap: 10px;
      align-items: baseline;
    }

    .realtimeHeader {
      border-bottom: 1px solid var(--line);
      padding-bottom: 8px;
    }

    .realtimeHeader span,
    .realtimeMeta {
      color: var(--muted);
      font-size: 11px;
    }

    .realtimeColumns {
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 10px;
    }

    .realtimeBlock {
      min-width: 0;
      padding-top: 8px;
      border-top: 1px solid var(--line);
    }

    .realtimeBlock h3 {
      margin: 0 0 6px;
      font-size: 12px;
    }

    .realtimeList {
      display: grid;
      gap: 5px;
      margin: 0;
      padding-left: 18px;
      font-size: 12px;
      line-height: 1.4;
    }

    .realtimeTranscript {
      max-height: 190px;
      overflow: auto;
      border-top: 1px solid var(--line);
      padding-top: 8px;
    }

    .realtimeSegment {
      display: grid;
      grid-template-columns: 82px minmax(0, 1fr);
      gap: 8px;
      padding: 5px 0;
      border-bottom: 1px dotted var(--line);
      font-size: 12px;
      line-height: 1.4;
    }

    .realtimeSegment strong,
    .realtimeSegment span {
      overflow-wrap: anywhere;
    }

    .realtimeMetrics {
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      gap: 6px;
    }

    .realtimeMetric {
      min-width: 0;
      padding: 7px;
      border: 1px solid var(--line);
      background: var(--surface);
    }

    .realtimeMetric strong,
    .realtimeMetric span {
      display: block;
      overflow-wrap: anywhere;
    }

    .realtimeMetric strong {
      font-size: 16px;
      line-height: 1.1;
    }

    .realtimeMetric span {
      margin-top: 3px;
      color: var(--muted);
      font-size: 10px;
    }

    .error {
      color: var(--red);
    }

    .cloudPanel {
      border-top: 3px solid var(--blue);
    }

    .cloudState {
      display: flex;
      align-items: center;
      gap: 8px;
      color: var(--muted);
      font-size: 12px;
    }

    .cloudDot {
      width: 8px;
      height: 8px;
      border-radius: 50%;
      background: var(--muted);
      flex: 0 0 auto;
    }

    .cloudDot.online { background: var(--green); }
    .cloudDot.warn { background: var(--amber); }
    .cloudDot.error { background: var(--red); }

    .cloudDevices {
      display: grid;
      gap: 6px;
      margin-top: 10px;
    }

    .cloudDevice {
      display: flex;
      justify-content: space-between;
      gap: 10px;
      padding: 8px 10px;
      border: 1px solid var(--line);
      background: #f7fafb;
      font-size: 12px;
    }

    .cloudDevice strong,
    .cloudDevice span { overflow-wrap: anywhere; }
    .cloudDevice span { color: var(--muted); text-align: right; }

    nav { display: flex; gap: 8px; padding: 12px 0 0; }
    nav button { min-height: 34px; padding: 6px 14px; background: transparent; color: var(--ink); border-color: var(--line); }
    nav button[aria-selected="true"] { background: var(--ink); color: #fffdf7; }
    .notesView { padding-top: 18px; }
    .notesHeader { display: flex; justify-content: space-between; align-items: end; gap: 12px; margin-bottom: 12px; }
    .notesHeader h2 { margin: 0; font-size: 20px; }
    .notesHeader p { margin: 4px 0 0; color: var(--muted); font-size: 12px; }
    .notesLayout { display: grid; grid-template-columns: minmax(230px, 0.72fr) minmax(0, 1.28fr); gap: 14px; align-items: start; }
    .notesListPanel, .noteFormPanel { min-width: 0; background: transparent; border: 0; border-radius: 0; box-shadow: none; }
    .notesListPanel, .noteFormPanel { overflow: hidden; }
    .notesListHead, .noteFormHead { display: flex; justify-content: space-between; align-items: center; gap: 8px; padding: 12px 14px; border-bottom: 1px solid var(--line); background: rgba(247, 244, 234, 0.72); }
    .notesListHead strong, .noteFormHead strong { font-size: 14px; }
    .notesListHead span, .noteFormHead span, .byteCount { color: var(--muted); font-size: 11px; }
    .notesList { display: grid; gap: 6px; padding: 10px; }
    .noteRow { display: grid; grid-template-columns: minmax(0, 1fr) auto; gap: 8px; align-items: center; padding: 8px; border: 1px solid transparent; border-radius: 6px; background: #fffefa; }
    .noteRow.selected { border-color: var(--green); background: #edf5ef; }
    .noteSelect { min-width: 0; padding: 5px 0; border: 0; background: transparent; color: var(--ink); text-align: left; font-weight: 700; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
    .noteSelect.completed { color: var(--muted); text-decoration: line-through; }
    .noteMeta { display: block; margin-top: 3px; color: var(--muted); font-size: 11px; font-weight: 500; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
    .noteRowActions { display: flex; gap: 4px; }
    .iconButton { width: 30px; min-height: 30px; padding: 4px; border-color: var(--line); background: transparent; color: var(--ink); font-size: 13px; }
    .noteEmpty { padding: 22px 14px; color: var(--muted); font-size: 13px; text-align: center; }
    .noteForm { display: grid; gap: 12px; padding: 14px; }
    .noteForm textarea { min-height: 180px; max-height: 42vh; font-family: inherit; font-size: 14px; }
    .noteCheck { display: flex; align-items: center; gap: 8px; color: var(--ink); font-size: 13px; }
    .noteCheck input { width: 18px; height: 18px; accent-color: var(--green); }
    .noteError { min-height: 20px; color: var(--red); font-size: 12px; line-height: 1.4; }
    .notesHidden { display: none; }
    @media (max-width: 700px) { .notesLayout { grid-template-columns: 1fr; } .notesHeader { align-items: start; flex-direction: column; } }

    @media (max-width: 860px) {
      .topbar,
      .layout,
      .grid2 {
        grid-template-columns: 1fr;
      }

      .status {
        justify-self: start;
        max-width: 100%;
      }

      .previewRail {
        position: static;
      }

      .controlPlane {
        grid-template-columns: minmax(0, 1fr) 36px;
      }

      .controlMetrics {
        grid-column: 1 / -1;
        grid-row: 2;
        border-top: 1px solid var(--line);
      }

      .controlRefresh {
        grid-column: 2;
        grid-row: 1;
      }
    }

    @media (max-width: 520px) {
      .topbar { gap: 10px; }

      h1 { font-size: 20px; }

      .status {
        width: fit-content;
        min-height: 32px;
        padding: 6px 9px;
      }

      nav {
        position: sticky;
        top: 0;
        z-index: 5;
        padding: 9px 0;
        border-bottom: 1px solid var(--line);
        background: var(--paper);
      }

      .panelHead > span { display: none; }

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

      .controlMetrics {
        grid-template-columns: repeat(2, minmax(0, 1fr));
      }

      .controlMetric:nth-child(odd) {
        border-left: 0;
      }

      .controlMetric:nth-child(n + 3) {
        border-top: 1px solid var(--line);
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
          <h1>GoTim Ink 会议控制台</h1>
          <p class="subtitle">极趣实验室 · 现场会议与墨水屏同步</p>
        </div>
      </div>
      <div id="status" class="status" role="status">正在读取会议数据...</div>
    </header>

    <section id="controlPlane" class="controlPlane" aria-label="现场运行状态" aria-live="polite">
      <div class="controlLead">
        <span class="controlEyebrow">现场控制面</span>
        <strong id="overviewMeeting">正在读取会议版本</strong>
        <span id="overviewUpdated">等待后台状态</span>
      </div>
      <dl class="controlMetrics">
        <div class="controlMetric"><dt>实时总结</dt><dd id="overviewTranscript">等待状态</dd></div>
        <div class="controlMetric"><dt>便利贴</dt><dd id="overviewNotes">等待状态</dd></div>
        <div class="controlMetric"><dt>云端设备</dt><dd id="overviewCloud">等待状态</dd></div>
        <div class="controlMetric"><dt>最近群发</dt><dd id="overviewFleet">尚未推送</dd></div>
      </dl>
      <button class="controlRefresh" type="button" title="刷新全部状态" aria-label="刷新全部状态" onclick="loadOverview()">↻</button>
    </section>

    <nav role="tablist" aria-label="工作区">
      <button id="meetingTab" role="tab" aria-selected="true" aria-controls="meetingView" onclick="showMeeting()">会议控制台</button>
      <button id="notesTab" role="tab" aria-selected="false" aria-controls="notesView" onclick="showNotes()">便利贴</button>
    </nav>
    <section id="meetingView" class="layout" role="tabpanel" aria-labelledby="meetingTab">
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
            <div id="realtimeOutput" class="realtimeOutput" aria-live="polite">
              <div class="realtimeHeader"><strong>实时结果</strong><span id="realtimeProvider">等待后台状态</span></div>
              <div id="realtimeAudioState" class="hint">尚未收到音频片段。</div>
              <div class="realtimeTranscript" id="realtimeTranscript"><div class="hint">开始录音或发送手工纪要后，这里会显示转写。</div></div>
              <div class="realtimeColumns">
                <section class="realtimeBlock"><h3>摘要与关键决定</h3><ul id="realtimeBullets" class="realtimeList"><li class="hint">暂无摘要</li></ul><ul id="realtimeDecisions" class="realtimeList"><li class="hint">暂无决定</li></ul></section>
                <section class="realtimeBlock"><h3>指标与待办</h3><div id="realtimeMetrics" class="realtimeMetrics"></div><ul id="realtimeActions" class="realtimeList"><li class="hint">暂无待办</li></ul></section>
              </div>
            </div>
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
        <section class="panel cloudPanel">
          <div class="panelHead">
            <h2>云端设备</h2>
            <span id="zectrixConnection">未检查</span>
          </div>
          <div class="body">
            <div class="cloudState"><i id="zectrixDot" class="cloudDot"></i><span id="zectrixDevices">正在读取云端状态...</span></div>
            <div id="zectrixDeviceList" class="cloudDevices"></div>
            <div class="actions">
              <button class="secondary" type="button" onclick="checkZectrixIntegration()">检查云端设备</button>
            </div>
            <p class="hint">后台从 ZECTRIX_API_KEY 或 ZECTRIX_API_KEY_FILE 读取密钥，不会进入浏览器或会议 JSON。</p>
          </div>
        </section>
      </aside>
    </section>
    <section id="notesView" class="notesView notesHidden" role="tabpanel" aria-labelledby="notesTab">
      <div class="notesHeader"><div><h2>我的便利贴</h2><p>保存在后台，设备联网后自动同步</p></div><button id="newNote" class="positive" type="button" onclick="selectNote(null)">新建便利贴</button></div>
      <div class="notesLayout">
        <section class="notesListPanel" aria-label="便利贴列表"><div class="notesListHead"><strong>便签列表</strong><span id="notesVersion">v0</span></div><div id="notesList" class="notesList"></div><p id="notesListEmpty" class="noteEmpty" hidden>还没有便利贴</p></section>
        <section class="noteFormPanel" aria-label="便利贴编辑器"><div class="noteFormHead"><strong id="noteEditorTitle">编辑便利贴</strong><span id="noteEditorState">未选择</span></div><p id="noteEditorEmpty" class="noteEmpty">选择一条便利贴，或新建一条。</p><form id="noteEditor" class="noteForm" onsubmit="saveNote(event)" hidden><div class="field"><label for="noteTitle">标题</label><input id="noteTitle" maxlength="48" autocomplete="off"><span id="noteTitleBytes" class="byteCount">0 / 48 bytes</span></div><div class="field"><label for="noteBody">内容</label><textarea id="noteBody" maxlength="384"></textarea><span id="noteBodyBytes" class="byteCount">0 / 384 bytes</span></div><label class="noteCheck"><input id="noteCompleted" type="checkbox">已完成</label><div class="field"><label for="noteRemindAt">提醒时间</label><input id="noteRemindAt" type="datetime-local"></div><div id="noteError" class="noteError" role="alert"></div><div class="actions"><button id="saveNoteButton" class="positive" type="submit">保存</button><button id="deleteNoteButton" class="secondary" type="button" onclick="deleteNote()">删除</button><button id="reloadStaleNote" class="secondary" type="button" onclick="reloadSelectedNote()" hidden>重新载入</button></div></form></section>
      </div>
    </section>
  </main>
  <script>
    let currentMeeting = {};
    const statusEl = document.getElementById("status");
    let mediaRecorder = null;
    let mediaStream = null;
    let recordingSessionId = null;
    let recordingSequence = 0;
    let eventSource = null, notesState={version:0,notes:[]}, selectedNoteId=null, noteFormDirty=false;
    let uploadChain = Promise.resolve();
    let overviewTimer = null;
    const MAX_NOTE_TITLE_BYTES = 48, MAX_NOTE_BODY_BYTES = 384;
    function showMeeting() {
      document.getElementById("meetingView").classList.remove("notesHidden");
      document.getElementById("notesView").classList.add("notesHidden");
      document.getElementById("meetingTab").setAttribute("aria-selected", "true");
      document.getElementById("notesTab").setAttribute("aria-selected", "false");
    }

    function showNotes() {
      document.getElementById("meetingView").classList.add("notesHidden");
      document.getElementById("notesView").classList.remove("notesHidden");
      document.getElementById("notesTab").setAttribute("aria-selected", "true");
      document.getElementById("meetingTab").setAttribute("aria-selected", "false");
      loadNotes();
    }

    function setRecordingButtons(state) {
      document.getElementById("startRecording").disabled = state !== "idle";
      document.getElementById("pauseRecording").disabled = state !== "recording";
      document.getElementById("resumeRecording").disabled = state !== "paused";
      document.getElementById("stopRecording").disabled = !["recording", "paused", "error"].includes(state);
      document.getElementById("recordingState").textContent = {
        idle: "等待录音；也可以直接发送手工纪要",
        recording: "录音进行中，音频按顺序上传后台",
        paused: "录音已暂停",
        finalizing: "正在等待 ASR 收尾并生成最终总结",
        error: "ASR 失败；已保留音频记录，可重试当前片段",
      }[state] || state;
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
      const sessionId = recordingSessionId;
      const audio_b64 = await blobToBase64(blob);
      await fetchJson(`/api/recordings/${sessionId}/chunks`, {
        method: "POST",
        body: JSON.stringify({
          sequence,
          meeting_id: currentMeeting.meeting_id || "meeting",
          speaker: document.getElementById("speakerLabel").value.trim() || "未知发言人",
          mime_type: mediaRecorder.mimeType,
          client_timestamp: new Date().toISOString(),
          audio_b64,
        })
      });
    }

    async function startRecordingSession() {
      try {
        mediaStream = await navigator.mediaDevices.getUserMedia({audio: true});
        mediaRecorder = new MediaRecorder(mediaStream);
        const created = await fetchJson("/api/recordings", {method: "POST", body: JSON.stringify({meeting_id: currentMeeting.meeting_id || "meeting", mime_type: mediaRecorder.mimeType})});
        recordingSessionId = created.session_id;
        recordingSequence = 0;
        uploadChain = Promise.resolve();
        mediaRecorder.ondataavailable = (event) => {
          uploadChain = uploadChain.then(() => uploadChunk(event.data));
          uploadChain.catch((error) => setStatus(`音频上传失败：${error.message}`, true));
        };
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
      const sessionId = recordingSessionId;
      if (!mediaRecorder || !sessionId) return;
      setRecordingButtons("finalizing");
      const stopped = new Promise((resolve) => mediaRecorder.addEventListener("stop", resolve, {once: true}));
      mediaRecorder.stop();
      mediaStream.getTracks().forEach((track) => track.stop());
      await stopped;
      try { await uploadChain; } catch (error) { setStatus(`音频上传失败，已保留可用片段：${error.message}`, true); }
      try {
        await fetchJson(`/api/recordings/${sessionId}/stop`, {method: "POST", body: "{}"});
        await loadMeeting();
      } catch (error) {
        setStatus(`结束录音失败：${error.message}`, true);
      } finally {
        recordingSessionId = null;
        mediaRecorder = null;
        mediaStream = null;
        setRecordingButtons("idle");
      }
    }

    function connectEvents() {
      if (eventSource) eventSource.close();
      eventSource = new EventSource("/api/events");
      ["transcript", "summary", "status", "meeting", "fleet"].forEach((name) => eventSource.addEventListener(name, () => loadMeeting({quiet: true})));
      eventSource.addEventListener("error", (event) => {
        let detail = "ASR 或后台处理失败";
        try { detail = JSON.parse(event.data).message || detail; } catch {}
        setStatus(detail, true);
        loadMeeting({quiet: true});
      });
      eventSource.addEventListener("fleet", () => loadOverview({quiet: true}));
      eventSource.addEventListener("notes", () => {
        loadNotes({preserveDirty: true});
        loadOverview({quiet: true});
      });
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
        const error = new Error(payload.error || `HTTP ${response.status}`);
        error.status = response.status;
        error.payload = payload;
        throw error;
      }
      return payload;
    }

    function overviewTime(value) {
      if (!value) return "等待首次保存";
      const date = new Date(value);
      return Number.isNaN(date.getTime()) ? String(value) : date.toLocaleTimeString([], {hour: "2-digit", minute: "2-digit"});
    }

    function renderOverview(overview) {
      const meeting = overview.meeting || {};
      const server = overview.server || {};
      const notes = overview.notes || {};
      const cloud = overview.zectrix || {};
      const fleet = overview.fleet || {};
      const lastPush = fleet.last_push || null;
      document.getElementById("overviewMeeting").textContent = (meeting.meeting_id || "local-demo") + " · v" + (meeting.version || 0);
      document.getElementById("overviewUpdated").textContent = "会议更新 " + overviewTime(meeting.updated_at);
      const asrMode = server.real_audio_transcription ? "实时 ASR" : "Demo ASR";
      document.getElementById("overviewTranscript").textContent = (meeting.transcript_status || "idle") + " · " + asrMode;
      document.getElementById("overviewNotes").textContent = (notes.count || 0) + " 条 · v" + (notes.version || 0);
      document.getElementById("overviewCloud").textContent = !cloud.configured
        ? "未配置密钥"
        : !cloud.reachable
          ? "连接异常"
          : (cloud.device_count || 0) + " 台在线";
      const fleetLabels = {pushed: "已全部推送", partial: "部分完成", error: "推送失败", no_devices: "暂无设备"};
      document.getElementById("overviewFleet").textContent = lastPush
        ? (fleetLabels[lastPush.status] || lastPush.status || "已记录") + " · " + overviewTime(lastPush.requested_at)
        : "尚未推送";
    }

    async function loadOverview({quiet = false} = {}) {
      try {
        const payload = await fetchJson("/api/overview");
        renderOverview(payload.data || {});
        if (!quiet) setStatus("后台状态已刷新");
        return payload.data;
      } catch (error) {
        if (!quiet) setStatus("后台状态读取失败：" + error.message, true);
        return null;
      }
    }

    function setNoteError(message = "") {
      document.getElementById("noteError").textContent = message;
    }

    function noteSize(value) {
      return new TextEncoder().encode(value).length;
    }

    function updateNoteByteCounts() {
      document.getElementById("noteTitleBytes").textContent = `${noteSize(noteTitle.value)} / ${MAX_NOTE_TITLE_BYTES} bytes`;
      document.getElementById("noteBodyBytes").textContent = `${noteSize(noteBody.value)} / ${MAX_NOTE_BODY_BYTES} bytes`;
    }

    function validateNoteForm() {
      updateNoteByteCounts();
      if (noteSize(noteTitle.value) > MAX_NOTE_TITLE_BYTES) throw new Error("标题超过 UTF-8 字节限制");
      if (noteSize(noteBody.value) > MAX_NOTE_BODY_BYTES) throw new Error("内容超过 UTF-8 字节限制");
    }

    function applyNotesSnapshot(data, preserveDirty = false) {
      notesState = data || {version: 0, notes: []};
      document.getElementById("notesVersion").textContent = `v${notesState.version || 0}`;
      renderNotes();
      if (!preserveDirty || !noteFormDirty) {
        const note = notesState.notes.find((item) => item.id === selectedNoteId);
        if (note) selectNote(note.id);
        else if (selectedNoteId) selectNote(null);
      }
    }

    async function loadNotes({preserveDirty = false} = {}) {
      try {
        applyNotesSnapshot(await fetchJson("/notes"), preserveDirty);
      } catch (error) {
        setNoteError(error.message);
      }
    }

    function renderNotes() {
      const list = document.getElementById("notesList");
      const empty = document.getElementById("notesListEmpty");
      empty.hidden = notesState.notes.length > 0;
      list.innerHTML = notesState.notes.map((note, index) => {
        const reminder = note.remind_at ? `提醒 ${escapeHtml(new Date(note.remind_at).toLocaleString())}` : "无提醒";
        return `<div class="noteRow ${note.id === selectedNoteId ? "selected" : ""}"><button class="noteSelect ${note.completed ? "completed" : ""}" type="button" onclick="selectNote('${note.id}')">${escapeHtml(note.title || "无标题")}<span class="noteMeta">${escapeHtml(reminder)}${note.completed ? " · 已完成" : ""}</span></button><div class="noteRowActions"><button class="iconButton" type="button" title="上移" aria-label="上移" ${index === 0 ? "disabled" : ""} onclick="moveNote('${note.id}', -1)">↑</button><button class="iconButton" type="button" title="下移" aria-label="下移" ${index === notesState.notes.length - 1 ? "disabled" : ""} onclick="moveNote('${note.id}', 1)">↓</button><button class="iconButton" type="button" title="删除" aria-label="删除" onclick="deleteNote('${note.id}')">×</button></div></div>`;
      }).join("");
    }

    function selectNote(id) {
      selectedNoteId = id;
      const note = notesState.notes.find((item) => item.id === id);
      const form = document.getElementById("noteEditor");
      const empty = document.getElementById("noteEditorEmpty");
      form.hidden = !id && id !== null;
      if (id === null) {
        form.hidden = false;
        empty.hidden = true;
        noteTitle.value = ""; noteBody.value = ""; noteCompleted.checked = false; noteRemindAt.value = "";
        document.getElementById("noteEditorTitle").textContent = "新建便利贴";
        document.getElementById("noteEditorState").textContent = "未保存";
      } else if (note) {
        form.hidden = false;
        empty.hidden = true;
        noteTitle.value = note.title || ""; noteBody.value = note.body || ""; noteCompleted.checked = !!note.completed; noteRemindAt.value = note.remind_at ? note.remind_at.slice(0, 16) : "";
        document.getElementById("noteEditorTitle").textContent = "编辑便利贴";
        document.getElementById("noteEditorState").textContent = note.completed ? "已完成" : "进行中";
      } else {
        form.hidden = true;
        empty.hidden = false;
        document.getElementById("noteEditorState").textContent = "未选择";
      }
      noteFormDirty = false;
      setNoteError();
      updateNoteByteCounts();
      renderNotes();
    }

    async function saveNote(event) {
      event.preventDefault();
      try {
        validateNoteForm();
        const payload = {title: noteTitle.value.trim(), body: noteBody.value, completed: noteCompleted.checked, remind_at: noteRemindAt.value ? new Date(noteRemindAt.value).toISOString() : null, base_version: notesState.version};
        const result = await fetchJson(selectedNoteId ? `/notes/${selectedNoteId}` : "/notes", {method: selectedNoteId ? "PATCH" : "POST", body: JSON.stringify(payload)});
        selectedNoteId = result.note?.id || selectedNoteId;
        noteFormDirty = false;
        applyNotesSnapshot(result.data);
        setNoteError();
      } catch (error) {
        if (error.status === 409) {
          document.getElementById("reloadStaleNote").hidden = false;
          applyNotesSnapshot(error.payload.data, true);
        }
        setNoteError(error.message);
      }
    }

    async function toggleNote(id) {
      try {
        const note = notesState.notes.find((item) => item.id === id);
        if (!note) return;
        const result = await fetchJson(`/notes/${id}`, {method: "PATCH", body: JSON.stringify({completed: !note.completed, base_version: notesState.version})});
        applyNotesSnapshot(result.data, true);
      } catch (error) { setNoteError(error.message); }
    }

    async function deleteNote(id = selectedNoteId) {
      if (!id || !window.confirm("删除这条便利贴？")) return;
      try {
        const result = await fetchJson(`/notes/${id}`, {method: "DELETE", body: JSON.stringify({base_version: notesState.version})});
        selectedNoteId = null;
        applyNotesSnapshot(result.data);
        selectNote(null);
      } catch (error) { setNoteError(error.message); }
    }

    async function moveNote(id, delta) {
      const ids = notesState.notes.map((note) => note.id);
      const from = ids.indexOf(id); const to = from + delta;
      if (from < 0 || to < 0 || to >= ids.length) return;
      [ids[from], ids[to]] = [ids[to], ids[from]];
      try {
        const result = await fetchJson("/notes/reorder", {method: "PUT", body: JSON.stringify({ids, base_version: notesState.version})});
        applyNotesSnapshot(result.data, true);
      } catch (error) { setNoteError(error.message); }
    }

    function reloadSelectedNote() {
      noteFormDirty = false;
      document.getElementById("reloadStaleNote").hidden = true;
      applyNotesSnapshot(notesState);
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

    function renderRealtime(meeting) {
      const transcript = meeting.transcript || {};
      const summary = meeting.summary || {};
      const audio = transcript.audio || {};
      if (recordingSessionId && ["recording", "paused", "finalizing", "error"].includes(transcript.status)) setRecordingButtons(transcript.status);
      const provider = document.getElementById("realtimeProvider");
      const audioState = document.getElementById("realtimeAudioState");
      provider.textContent = "状态：" + (transcript.status || "idle") + (summary.final ? " · 已完成" : "");
      if (transcript.error) {
        audioState.textContent = "处理失败：" + (transcript.error.message || "未知错误") + "；已保留 " + (audio.accepted_chunks || 0) + " 个已接收片段，可重试。";
        audioState.classList.add("error");
      } else if (audio.accepted_chunks) {
        audioState.textContent = "后台已接收 " + audio.accepted_chunks + " 个音频片段，共 " + (audio.bytes || 0) + " bytes。" + (transcript.segments?.length ? "已生成转写。" : "当前 Demo ASR 未返回文字，请配置真实 ASR 或使用手工纪要。");
        audioState.classList.remove("error");
      } else {
        audioState.textContent = "尚未收到音频片段。";
        audioState.classList.remove("error");
      }
      const segments = transcript.segments || [];
      document.getElementById("realtimeTranscript").innerHTML = segments.slice(-20).map((item) => "<div class=\"realtimeSegment\"><strong>" + escapeHtml(item.speaker || "未知发言人") + "</strong><span>" + escapeHtml(item.text || "") + "</span></div>").join("") || "<div class=\"hint\">开始录音或发送手工纪要后，这里会显示转写。</div>";
      const bullets = summary.bullets || [];
      document.getElementById("realtimeBullets").innerHTML = bullets.map((item) => "<li>" + escapeHtml(item) + "</li>").join("") || "<li class=\"hint\">暂无摘要</li>";
      const decisions = summary.decisions || [];
      document.getElementById("realtimeDecisions").innerHTML = decisions.map((item) => "<li>" + escapeHtml(item) + "</li>").join("") || "<li class=\"hint\">暂无决定</li>";
      const metrics = summary.metrics || [];
      document.getElementById("realtimeMetrics").innerHTML = metrics.map((item) => "<div class=\"realtimeMetric\"><strong>" + escapeHtml(item.value || "--") + "</strong><span>" + escapeHtml(item.label || "指标") + " · " + escapeHtml(item.delta || "") + "</span></div>").join("") || "<div class=\"hint\">暂无指标</div>";
      const actions = summary.action_items || [];
      document.getElementById("realtimeActions").innerHTML = actions.map((item) => "<li>" + escapeHtml(item.task || item.text || item) + (item.owner ? " · " + escapeHtml(item.owner) : "") + "</li>").join("") || "<li class=\"hint\">暂无待办</li>";
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
      renderRealtime(currentMeeting);
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

    async function loadMeeting({quiet = false} = {}) {
      try {
        if (!quiet) setStatus("正在读取会议数据...");
        const payload = await fetchJson("/meeting/current");
        fillForm(payload.data);
        if (!quiet) setStatus("已读取：" + (payload.data.meeting_id || "local-demo"));
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
        loadOverview({quiet: true});
        setStatus("基本信息已保存");
      } catch (error) {
        setStatus(error.message, true);
      }
    }

    async function checkZectrixIntegration() {
      const connection = document.getElementById("zectrixConnection");
      const devices = document.getElementById("zectrixDevices");
      const list = document.getElementById("zectrixDeviceList");
      const dot = document.getElementById("zectrixDot");
      try {
        const payload = await fetchJson("/api/integrations/zectrix");
        list.innerHTML = "";
        dot.className = "cloudDot";
        if (!payload.configured) {
          connection.textContent = "未配置";
          devices.textContent = "未配置云端密钥；可设置 ZECTRIX_API_KEY 或 ZECTRIX_API_KEY_FILE。";
          dot.classList.add("warn");
          return payload;
        }
        connection.textContent = "已配置";
        dot.classList.add("online");
        devices.textContent = "已连接云端 · " + (payload.device_count || 0) + " 台设备";
        list.innerHTML = (payload.devices || []).map((item) => "<div class=\"cloudDevice\"><strong>" + escapeHtml(item.alias || item.device_id) + "</strong><span>" + escapeHtml(item.device_id) + (item.board ? " · " + escapeHtml(item.board) : "") + "</span></div>").join("") || "<div class=\"hint\">API key 有效，但没有绑定设备。</div>";
        return payload;
      } catch (error) {
        connection.textContent = "连接失败";
        devices.textContent = error.message;
        dot.className = "cloudDot error";
        list.innerHTML = "";
        throw error;
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
        const delivery = payload.delivery || {};
        const pushed = (delivery.targets || []).filter((item) => item.status === "pushed").length;
        const message = delivery.status === "pushed"
          ? "已推送 " + pushed + " 台设备"
          : delivery.reason === "api_key_missing"
            ? "未配置 ZECTRIX_API_KEY；已保存本地群发记录"
            : delivery.status === "partial"
              ? "部分设备推送完成，请检查云端状态"
              : "暂无可推送设备；已记录请求";
        setStatus(message, delivery.status === "error");
        loadOverview({quiet: true});
        checkZectrixIntegration().catch(() => {});
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
        loadOverview({quiet: true});
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

    ["noteTitle", "noteBody", "noteCompleted", "noteRemindAt"].forEach((id) => document.getElementById(id).addEventListener("input", () => {
      noteFormDirty = true;
      updateNoteByteCounts();
    }));
    setRecordingButtons("idle");
    connectEvents();
    loadMeeting();
    loadOverview();
    overviewTimer = window.setInterval(() => loadOverview({quiet: true}), 30000);
    checkZectrixIntegration().catch(() => {});
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
    protocol_version = "HTTP/1.1"
    data_path: Path = DEFAULT_DATA
    file_root: Path = DEFAULT_FILES
    note_store_path: Path = DEFAULT_NOTES
    realtime_manager = None
    realtime_asr_provider = None
    zectrix_client = None
    note_store = None
    _note_store_lock = threading.RLock()

    @classmethod
    def reset_realtime_runtime(cls) -> None:
        cls.realtime_manager = None

    @classmethod
    def get_realtime_manager(cls) -> RecordingManager:
        manager = cls.realtime_manager
        if manager is None or manager.store.path != cls.data_path:
            manager = RecordingManager(
                VersionedMeetingStore(cls.data_path),
                asr=cls.realtime_asr_provider or build_asr_provider(),
            )
            cls.realtime_manager = manager
        return manager

    @classmethod
    def get_zectrix_client(cls):
        if cls.zectrix_client is None:
            cls.zectrix_client = build_zectrix_client()
        return cls.zectrix_client

    @classmethod
    def get_note_store(cls) -> VersionedNoteStore:
        with cls._note_store_lock:
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
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            self.send_json(400, {"ok": False, "error": "invalid_content_length"})
            return None
        if length < 0 or length > MAX_JSON_BODY_BYTES:
            self.send_json(413, {"ok": False, "error": "request_body_too_large"})
            return None
        try:
            raw = self.rfile.read(length)
            payload = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
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
        manager = self.get_realtime_manager()
        before = manager.store.read()

        def replace(candidate: dict) -> None:
            candidate.clear()
            candidate.update(payload)

        result = manager.store.mutate(replace)
        if int(result.get("version", 0)) != int(before.get("version", 0)):
            manager.broker.publish("meeting", result.get("version", 0), {"data": result})
        return result

    def zectrix_status(self) -> dict:
        client = self.get_zectrix_client()
        base = {
            "configured": bool(getattr(client, "configured", False)),
            "credential_source": getattr(client, "credential_source", "injected"),
            "api_base": getattr(client, "base_url", ""),
            "auth": "X-API-Key",
            "reachable": False,
            "devices": [],
            "device_count": 0,
        }
        if not base["configured"]:
            return {**base, "reason": "api_key_missing", "checked_at": now_iso()}
        try:
            if callable(getattr(client, "check", None)):
                result = client.check()
                raw_devices = result.get("devices") if isinstance(result, dict) else []
                base.update({key: value for key, value in result.items() if key != "devices"})
            else:
                raw_devices = client.list_devices()
                base.update({"reachable": True, "reason": "ok" if raw_devices else "no_devices"})
        except ZectrixCloudError as error:
            return {**base, "reason": "zectrix_api_failed", "error": str(error), "checked_at": now_iso()}

        devices = [
            {
                "device_id": item.get("deviceId") or item.get("device_id"),
                "alias": item.get("alias") or item.get("name") or "未命名设备",
                "board": item.get("board") or "",
            }
            for item in (raw_devices or [])
            if isinstance(item, dict) and (item.get("deviceId") or item.get("device_id"))
        ]
        base["devices"] = devices
        base["device_count"] = len(devices)
        base["checked_at"] = now_iso()
        return base

    def overview(self) -> dict:
        manager = self.get_realtime_manager()
        meeting = self.current_meeting()
        notes = self.get_note_store().read()
        transcript = meeting.get("transcript") if isinstance(meeting.get("transcript"), dict) else {}
        summary = meeting.get("summary") if isinstance(meeting.get("summary"), dict) else {}
        fleet = meeting.get("fleet") if isinstance(meeting.get("fleet"), dict) else {}
        history = fleet.get("history") if isinstance(fleet.get("history"), list) else []
        return {
            "server": {
                "checked_at": now_iso(),
                "asr_provider": getattr(manager.asr, "name", manager.asr.__class__.__name__),
                "real_audio_transcription": bool(getattr(manager.asr, "supports_audio", False)),
            },
            "meeting": {
                "meeting_id": meeting.get("meeting_id") or "local-demo",
                "version": int(meeting.get("version", 0)),
                "updated_at": meeting.get("updated_at") or "",
                "update_priority": meeting.get("update_priority") or "normal",
                "transcript_status": transcript.get("status") or "idle",
                "summary_updated_at": summary.get("updated_at") or "",
                "summary_final": bool(summary.get("final", False)),
            },
            "notes": {
                "version": int(notes.get("version", 0)),
                "count": len(notes.get("notes") or []),
                "updated_at": notes.get("updated_at") or "",
            },
            "zectrix": self.zectrix_status(),
            "fleet": {
                "last_push": fleet.get("last_push") if isinstance(fleet.get("last_push"), dict) else None,
                "history": history[-20:],
            },
        }

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
        try:
            if action == "create":
                result = store.create_with_result(payload, base_version)
            elif action == "patch":
                result = store.patch_with_result(note_id or "", payload, base_version)
            elif action == "delete":
                result = store.delete_with_result(note_id or "", base_version)
            else:
                result = store.reorder_with_result(payload.get("ids"), base_version)
        except (NoteValidationError, VersionConflictError, KeyError) as error:
            self.send_note_error(error)
            return

        snapshot = result.snapshot
        version = int(snapshot.get("version", 0))
        if result.changed:
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
            manager = self.get_realtime_manager()
            self.send_json(200, {
                "ok": True,
                "asr_provider": getattr(manager.asr, "name", manager.asr.__class__.__name__),
                "real_audio_transcription": bool(getattr(manager.asr, "supports_audio", False)),
            })
            return
        if path == "/api/overview":
            self.send_json(200, {"ok": True, "data": self.overview()})
            return
        if path == "/api/integrations/zectrix":
            self.send_json(200, {"ok": True, **self.zectrix_status()})
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
            try:
                last_id = int(self.headers.get("Last-Event-ID", "0") or 0)
            except ValueError:
                last_id = 0
            broker = self.get_realtime_manager().broker
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream; charset=utf-8")
            self.send_header("Cache-Control", "no-cache")
            self.send_header("Connection", "keep-alive")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            try:
                while True:
                    events = broker.wait_events_after(last_id, timeout=15.0)
                    if events:
                        self.wfile.write(format_sse(events))
                        self.wfile.flush()
                        last_id = events[-1]["id"]
                    else:
                        self.wfile.write(b": keep-alive\n\n")
                        self.wfile.flush()
            except (BrokenPipeError, ConnectionResetError, OSError):
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
            try:
                session, state = manager.create(
                    str(payload.get("meeting_id") or "meeting"),
                    str(payload.get("mime_type") or "audio/webm"),
                )
            except ValueError as error:
                self.send_json(400, {"ok": False, "error": str(error)})
                return
            self.send_json(201, {"ok": True, "session_id": session.session_id, "version": state.get("version", 0), "status": session.status, "mime_type": session.mime_type})
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
                    try:
                        sequence = int(payload.get("sequence", -1))
                    except (TypeError, ValueError):
                        self.send_json(400, {"ok": False, "error": "sequence_must_be_integer"})
                        return
                    encoded = payload.get("audio_b64")
                    if encoded is None:
                        if payload.get("test_text"):
                            chunk = b""
                        else:
                            self.send_json(400, {"ok": False, "error": "audio_b64_required"})
                            return
                    elif not isinstance(encoded, str):
                        self.send_json(400, {"ok": False, "error": "audio_b64_must_be_string"})
                        return
                    else:
                        try:
                            chunk = base64.b64decode(encoded, validate=True)
                        except (ValueError, binascii.Error):
                            self.send_json(400, {"ok": False, "error": "invalid_audio_base64"})
                            return
                    if len(chunk) > MAX_AUDIO_CHUNK_BYTES:
                        self.send_json(413, {"ok": False, "error": "audio_chunk_too_large"})
                        return
                    result = manager.accept_chunk(session_id, sequence, chunk, payload)
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
            except AsrProviderError as error:
                state = manager.store.read()
                self.send_json(503, {"ok": False, "error": "asr_failed", "message": str(error), "retryable": error.retryable, "version": state.get("version", 0)})
            except KeyError:
                self.send_json(404, {"ok": False, "error": "session_not_found"})
            except (TypeError, ValueError) as error:
                code = 400 if str(error) in {"audio_chunk_empty", "audio_chunk_too_large", "mime_type_mismatch", "meeting_id_mismatch", "unsupported_audio_mime_type"} else 409
                self.send_json(code, {"ok": False, "error": str(error)})
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
            requested = unwrap_meeting_payload(payload)
            meeting = self.current_meeting()
            meeting.update(requested)
            live = meeting.setdefault("live", {})
            push_id = uuid.uuid4().hex
            live["remote_update"] = "母机同步全部设备"
            fleet = meeting.setdefault("fleet", {})
            client = self.get_zectrix_client()
            targets = []
            cloud_error = ""
            push_started = time.monotonic()
            if getattr(client, "configured", False):
                try:
                    devices = client.list_devices()
                    pages = build_meeting_pages(meeting)
                    for device in devices:
                        device_id = str(device.get("deviceId") or device.get("device_id") or "")
                        if not device_id:
                            continue
                        target_started = time.monotonic()
                        target = {
                            "device_id": device_id,
                            "alias": device.get("alias") or "未命名设备",
                            "status": "pushing",
                            "pages_pushed": 0,
                            "attempts": 0,
                            "pages": [],
                        }
                        try:
                            for page in pages:
                                page_started = time.monotonic()
                                try:
                                    client.push_structured_text(device_id, page["title"], page["body"], page["page_id"])
                                except ZectrixCloudError as error:
                                    target["attempts"] += max(1, int(getattr(client, "last_attempts", 1)))
                                    target["pages"].append({
                                        "page_id": page["page_id"],
                                        "status": "error",
                                        "duration_ms": int((time.monotonic() - page_started) * 1000),
                                        "error": str(error),
                                    })
                                    raise
                                target["attempts"] += max(1, int(getattr(client, "last_attempts", 1)))
                                target["pages_pushed"] += 1
                                target["pages"].append({
                                    "page_id": page["page_id"],
                                    "status": "pushed",
                                    "duration_ms": int((time.monotonic() - page_started) * 1000),
                                })
                            target["status"] = "pushed"
                        except ZectrixCloudError as error:
                            target["status"] = "error"
                            target["error"] = str(error)
                            cloud_error = str(error)
                        target["duration_ms"] = int((time.monotonic() - target_started) * 1000)
                        targets.append(target)
                except ZectrixCloudError as error:
                    cloud_error = str(error)
            else:
                registered = fleet.get("devices") if isinstance(fleet.get("devices"), list) else []
                targets = [
                    {
                        "device_id": str(device.get("device_id") or device.get("id") or "unknown"),
                        "status": "queued" if device.get("online", False) else "offline",
                        "pages_pushed": 0,
                    }
                    for device in registered
                    if isinstance(device, dict)
                ]
            if cloud_error and not targets:
                delivery_status = "error"
                delivery_reason = "zectrix_api_failed"
            elif getattr(client, "configured", False) and targets and all(item.get("status") == "pushed" for item in targets):
                delivery_status = "pushed"
                delivery_reason = "ok"
            elif getattr(client, "configured", False) and targets:
                delivery_status = "partial"
                delivery_reason = "zectrix_api_failed" if cloud_error else "device_push_partial"
            else:
                delivery_status = "no_devices"
                delivery_reason = "api_key_missing" if not getattr(client, "configured", False) else "no_devices"
            delivery = {
                "push_id": push_id,
                "status": delivery_status,
                "reason": delivery_reason,
                "requested_at": now_iso(),
                "duration_ms": int((time.monotonic() - push_started) * 1000),
                "targets": targets,
            }
            fleet["last_push"] = delivery
            history = fleet.get("history") if isinstance(fleet.get("history"), list) else []
            fleet["history"] = (history + [delivery])[-20:]
            meeting = self.save_current_meeting(meeting)
            manager.broker.publish("fleet", meeting.get("version", 0), {"delivery": delivery})
            self.send_json(200, {"ok": True, "data": meeting, "delivery": delivery})
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
            keywords = payload.get("keywords")
            if keywords is not None and (not isinstance(keywords, list) or not all(isinstance(item, str) for item in keywords)):
                self.send_json(400, {"ok": False, "error": "keywords_must_be_array"})
                return
            state = manager.append_manual_segments(segments, keywords)
            self.send_json(200, {"ok": True, "data": state})
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
