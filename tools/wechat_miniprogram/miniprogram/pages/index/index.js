const SERVICE_UUID = "6E3F0010-2A1B-4F2E-8C5D-1234567890AB";
const MEETING_UUID = "6E3F0011-2A1B-4F2E-8C5D-1234567890AB";
const STATUS_UUID = "6E3F0013-2A1B-4F2E-8C5D-1234567890AB";
const PROVISION_UUID = "6E3F0014-2A1B-4F2E-8C5D-1234567890AB";

const FLAG_FIRST = 0x01;
const FLAG_LAST = 0x02;
const DEFAULT_WRITE_BYTES = 20;

const sampleMeeting = {
  meeting_id: "iphone-demo",
  updated_at: "2026-07-09T10:00:00+08:00",
  home: {
    title: "极趣实验室 Note",
    date_label: "07/09 周四",
    month: "JUL",
    day: "09",
    weekday: "周四"
  },
  device_status: {
    network: "BLE",
    mode: "iPhone",
    nfc: "Ready",
    battery: "--"
  },
  attendee: {
    id: "guest-001",
    name: "客户嘉宾",
    role: "Demo"
  },
  current_agenda_index: 0,
  agenda: [
    {
      time: "10:00",
      title: "产品开场",
      speaker: "Jasper",
      note: "墨水屏会议助手"
    },
    {
      time: "10:15",
      title: "资料扫码",
      speaker: "客户",
      note: "扫码下载 PDF"
    },
    {
      time: "10:30",
      title: "AI 摘要",
      speaker: "会议助手",
      note: "会后同步"
    }
  ],
  materials: {
    label: "会议资料",
    url: "https://msh.cn/m"
  },
  interaction: {
    label: "提交问题",
    url: "https://msh.cn/q"
  },
  summary: {
    title: "实时摘要",
    bullets: [
      "客户关注 iPhone 直接更新议程。",
      "二维码用于下载资料和会后总结。",
      "后续接入录音、说话人标签和火山 API。"
    ],
    keywords: ["蓝牙", "小程序", "会议助手"]
  },
  reminder: {
    url: "https://msh.cn/r",
    items: [
      {
        time: "10:30",
        title: "发送会后纪要"
      }
    ]
  }
};

function openBluetoothAdapter() {
  return new Promise((resolve, reject) => {
    wx.openBluetoothAdapter({
      success: resolve,
      fail: reject
    });
  });
}

function startBluetoothDevicesDiscovery(options) {
  return new Promise((resolve, reject) => {
    wx.startBluetoothDevicesDiscovery({
      ...options,
      success: resolve,
      fail: reject
    });
  });
}

function stopBluetoothDevicesDiscovery() {
  return new Promise((resolve, reject) => {
    wx.stopBluetoothDevicesDiscovery({
      success: resolve,
      fail: reject
    });
  });
}

function createBLEConnection(options) {
  return new Promise((resolve, reject) => {
    wx.createBLEConnection({
      ...options,
      success: resolve,
      fail: reject
    });
  });
}

function getBLEDeviceServices(options) {
  return new Promise((resolve, reject) => {
    wx.getBLEDeviceServices({
      ...options,
      success: resolve,
      fail: reject
    });
  });
}

function getBLEDeviceCharacteristics(options) {
  return new Promise((resolve, reject) => {
    wx.getBLEDeviceCharacteristics({
      ...options,
      success: resolve,
      fail: reject
    });
  });
}

function notifyBLECharacteristicValueChange(options) {
  return new Promise((resolve, reject) => {
    wx.notifyBLECharacteristicValueChange({
      ...options,
      success: resolve,
      fail: reject
    });
  });
}

function writeBLECharacteristicValue(options) {
  return new Promise((resolve, reject) => {
    wx.writeBLECharacteristicValue({
      ...options,
      success: resolve,
      fail: reject
    });
  });
}

function requestJson(url, method, data) {
  return new Promise((resolve, reject) => {
    wx.request({
      url,
      method,
      data,
      header: {
        "content-type": "application/json"
      },
      success: (res) => {
        if (res.statusCode >= 200 && res.statusCode < 300 && res.data && res.data.ok) {
          resolve(res.data);
        } else {
          reject(new Error(`HTTP ${res.statusCode}: ${JSON.stringify(res.data)}`));
        }
      },
      fail: reject
    });
  });
}

function normalizeUuid(value) {
  return String(value || "").toUpperCase();
}

function sameUuid(left, right) {
  return normalizeUuid(left) === normalizeUuid(right);
}

function findCharacteristic(characteristics, targetUuid) {
  const found = (characteristics || []).find((item) => sameUuid(item.uuid, targetUuid));
  if (!found) {
    throw new Error(`characteristic not found: ${targetUuid}`);
  }
  return found.uuid;
}

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function utf8Bytes(value) {
  const encoded = encodeURIComponent(value);
  const out = [];
  for (let i = 0; i < encoded.length; i += 1) {
    if (encoded[i] === "%") {
      out.push(parseInt(encoded.slice(i + 1, i + 3), 16));
      i += 2;
    } else {
      out.push(encoded.charCodeAt(i));
    }
  }
  return out;
}

function bytesToArrayBuffer(bytes) {
  const buffer = new ArrayBuffer(bytes.length);
  new Uint8Array(buffer).set(bytes);
  return buffer;
}

function stringToArrayBuffer(value) {
  return bytesToArrayBuffer(utf8Bytes(value));
}

function decodeStatus(buffer) {
  const view = new Uint8Array(buffer);
  const idBytes = Array.from(view.slice(2)).filter((item) => item !== 0);
  return {
    state: view[0] || 0,
    code: view[1] || 0,
    id: decodeURIComponent(idBytes.map((item) => `%${item.toString(16).padStart(2, "0")}`).join(""))
  };
}

function encodeMeetingFrames(jsonText, maxWriteBytes = DEFAULT_WRITE_BYTES) {
  const payload = utf8Bytes(JSON.stringify(JSON.parse(jsonText)));
  const chunkSize = Math.min(maxWriteBytes - 3, 255);
  const frames = [];
  let offset = 0;
  let seq = 0;

  if (payload.length === 0) {
    return [bytesToArrayBuffer([0, FLAG_FIRST | FLAG_LAST, 0])];
  }

  while (offset < payload.length) {
    const chunk = payload.slice(offset, offset + chunkSize);
    let flags = 0;
    if (offset === 0) {
      flags |= FLAG_FIRST;
    }
    offset += chunk.length;
    if (offset >= payload.length) {
      flags |= FLAG_LAST;
    }
    frames.push(bytesToArrayBuffer([seq, flags, chunk.length, ...chunk]));
    seq = (seq + 1) & 0xff;
  }
  return frames;
}

Page({
  data: {
    devices: [],
    connected: false,
    deviceId: "",
    deviceName: "",
    serviceId: "",
    meetingCharacteristicId: "",
    statusCharacteristicId: "",
    provisionCharacteristicId: "",
    statusText: "未连接",
    ssid: "",
    password: "",
    meetingUrl: "http://172.20.10.10:8787/meeting/current",
    serverUrl: "http://172.20.10.10:8787",
    meetingJson: JSON.stringify(sampleMeeting, null, 2),
    logs: []
  },

  log(message) {
    const time = new Date().toLocaleTimeString();
    this.setData({
      logs: [`${time} ${message}`, ...this.data.logs].slice(0, 8)
    });
  },

  onUnload() {
    this.stopScan();
    if (this.data.deviceId) {
      wx.closeBLEConnection({ deviceId: this.data.deviceId });
    }
    wx.closeBluetoothAdapter();
  },

  onSsidInput(event) {
    this.setData({ ssid: event.detail.value });
  },

  onPasswordInput(event) {
    this.setData({ password: event.detail.value });
  },

  onMeetingUrlInput(event) {
    this.setData({ meetingUrl: event.detail.value });
  },

  onServerUrlInput(event) {
    this.setData({ serverUrl: event.detail.value });
  },

  onMeetingJsonInput(event) {
    this.setData({ meetingJson: event.detail.value });
  },

  async startScan() {
    try {
      await openBluetoothAdapter();
      this.setData({ devices: [], statusText: "扫描中" });
      wx.onBluetoothDeviceFound((res) => {
        const found = (res.devices || []).filter((device) => {
          const name = device.name || device.localName || "";
          const services = (device.advertisServiceUUIDs || []).map((item) => item.toUpperCase());
          return name.includes("GoTim") || services.includes(SERVICE_UUID);
        });
        if (!found.length) {
          return;
        }
        const devices = [...this.data.devices];
        found.forEach((device) => {
          if (!devices.some((item) => item.deviceId === device.deviceId)) {
            devices.push({
              deviceId: device.deviceId,
              name: device.name || device.localName || "GoTim-ink"
            });
          }
        });
        this.setData({ devices });
      });
      await startBluetoothDevicesDiscovery({
        allowDuplicatesKey: true
      });
      this.log("BLE 扫描已开始");
    } catch (error) {
      this.log(`扫描失败: ${error.errMsg || error}`);
      this.setData({ statusText: "扫描失败" });
    }
  },

  async stopScan() {
    try {
      await stopBluetoothDevicesDiscovery();
      if (!this.data.connected) {
        this.setData({ statusText: "未连接" });
      }
    } catch (error) {
      // Ignore "not discovering" errors.
    }
  },

  async discoverGotimService(deviceId) {
    const serviceResult = await getBLEDeviceServices({ deviceId });
    const services = serviceResult.services || [];
    const service = services.find((item) => sameUuid(item.uuid, SERVICE_UUID));
    if (!service) {
      const names = services.map((item) => item.uuid).join(", ");
      throw new Error(`service not found: ${names || "empty"}`);
    }
    return service.uuid;
  },

  async connectDevice(event) {
    const deviceId = event.currentTarget.dataset.id;
    const deviceName = event.currentTarget.dataset.name || "GoTim-ink";
    try {
      await this.stopScan();
      this.setData({ statusText: "连接中" });
      await createBLEConnection({ deviceId, timeout: 10000 });
      await sleep(500);
      const serviceId = await this.discoverGotimService(deviceId);
      const characteristicResult = await getBLEDeviceCharacteristics({ deviceId, serviceId });
      const characteristics = characteristicResult.characteristics || [];
      const meetingCharacteristicId = findCharacteristic(characteristics, MEETING_UUID);
      const statusCharacteristicId = findCharacteristic(characteristics, STATUS_UUID);
      const provisionCharacteristicId = findCharacteristic(characteristics, PROVISION_UUID);
      await notifyBLECharacteristicValueChange({
        deviceId,
        serviceId,
        characteristicId: statusCharacteristicId,
        state: true
      });
      wx.onBLECharacteristicValueChange((res) => {
        if (!sameUuid(res.characteristicId, this.data.statusCharacteristicId || STATUS_UUID)) {
          return;
        }
        const status = decodeStatus(res.value);
        this.setData({ statusText: `状态 ${status.state}/${status.code} ${status.id}` });
      });
      this.setData({
        connected: true,
        deviceId,
        deviceName,
        serviceId,
        meetingCharacteristicId,
        statusCharacteristicId,
        provisionCharacteristicId,
        statusText: "已连接"
      });
      this.log(`已连接 ${deviceName}`);
    } catch (error) {
      this.log(`连接失败: ${error.errMsg || error}`);
      this.setData({ connected: false, statusText: "连接失败" });
    }
  },

  async writeCharacteristic(characteristicId, value) {
    if (!this.data.connected) {
      throw new Error("device not connected");
    }
    await writeBLECharacteristicValue({
      deviceId: this.data.deviceId,
      serviceId: this.data.serviceId,
      characteristicId,
      value
    });
    await sleep(60);
  },

  async sendProvision() {
    const ssid = this.data.ssid.trim();
    if (!ssid) {
      this.log("请填写 SSID");
      return;
    }
    const payload = {
      ssid,
      password: this.data.password,
      meeting_url: this.data.meetingUrl.trim()
    };
    try {
      await this.writeCharacteristic(this.data.provisionCharacteristicId, stringToArrayBuffer(JSON.stringify(payload)));
      this.log("Provision 已写入");
    } catch (error) {
      this.log(`Provision 失败: ${error.errMsg || error}`);
    }
  },

  async sendMeeting() {
    try {
      const frames = encodeMeetingFrames(this.data.meetingJson);
      for (const frame of frames) {
        await this.writeCharacteristic(this.data.meetingCharacteristicId, frame);
      }
      this.log(`Meeting 已写入 ${frames.length} 帧`);
    } catch (error) {
      this.log(`Meeting 失败: ${error.errMsg || error}`);
    }
  },

  async syncMeetingToServer() {
    const base = this.data.serverUrl.replace(/\/$/, "");
    try {
      const meeting = JSON.parse(this.data.meetingJson);
      const result = await requestJson(`${base}/meeting/current`, "POST", meeting);
      this.setData({ meetingJson: JSON.stringify(result.data, null, 2) });
      this.log("会议已同步到服务端");
    } catch (error) {
      this.log(`服务端同步失败: ${error.errMsg || error}`);
    }
  },

  async fetchMeetingFromServer() {
    const base = this.data.serverUrl.replace(/\/$/, "");
    try {
      const result = await requestJson(`${base}/meeting/current`, "GET");
      this.setData({ meetingJson: JSON.stringify(result.data, null, 2) });
      this.log("已拉取服务端会议");
    } catch (error) {
      this.log(`拉取服务端失败: ${error.errMsg || error}`);
    }
  },

  async sendTranscriptDemo() {
    const base = this.data.serverUrl.replace(/\/$/, "");
    try {
      const result = await requestJson(`${base}/meeting/transcript`, "POST", {
        segments: [
          { speaker: "Jasper", text: "客户需要只带 iPhone 和墨水屏完成演示。" },
          { speaker: "客户", text: "二维码要能下载会议资料和会后总结。" },
          { speaker: "会议助手", text: "会后生成摘要，并把个人提醒同步到设备。" }
        ],
        keywords: ["iPhone", "二维码", "会议摘要"]
      });
      this.setData({ meetingJson: JSON.stringify(result.data, null, 2) });
      this.log("转写摘要已写入服务端");
    } catch (error) {
      this.log(`转写摘要失败: ${error.errMsg || error}`);
    }
  }
});
