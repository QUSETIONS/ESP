#include "note_data.h"

#include <algorithm>
#include <cstring>
#include <limits>

namespace gotim {
namespace {

void AppendU16(std::vector<uint8_t>* out, uint16_t value) {
    out->push_back(static_cast<uint8_t>(value & 0xff));
    out->push_back(static_cast<uint8_t>((value >> 8) & 0xff));
}

void AppendU64(std::vector<uint8_t>* out, uint64_t value) {
    for (unsigned shift = 0; shift < 64; shift += 8) {
        out->push_back(static_cast<uint8_t>((value >> shift) & 0xff));
    }
}

void AppendBytes(std::vector<uint8_t>* out, const char* bytes, size_t length) {
    out->insert(out->end(), bytes, bytes + length);
}

bool ReadU16(const uint8_t* data, size_t length, size_t* offset, uint16_t* value) {
    if (*offset + 2 > length) return false;
    *value = static_cast<uint16_t>(data[*offset]) |
             static_cast<uint16_t>(data[*offset + 1] << 8);
    *offset += 2;
    return true;
}

bool ReadU64(const uint8_t* data, size_t length, size_t* offset, uint64_t* value) {
    if (*offset + 8 > length) return false;
    *value = 0;
    for (unsigned shift = 0; shift < 64; shift += 8) {
        *value |= static_cast<uint64_t>(data[*offset + shift / 8]) << shift;
    }
    *offset += 8;
    return true;
}

bool ReadBytes(const uint8_t* data, size_t length, size_t* offset, char* out,
               size_t capacity, uint16_t size) {
    if (size > capacity || *offset + size > length) return false;
    std::fill(out, out + capacity + 1, '\0');
    std::memcpy(out, data + *offset, size);
    *offset += size;
    return true;
}

void AppendNote(std::vector<uint8_t>* out, const NoteData& note) {
    AppendU16(out, note.title_length);
    AppendU16(out, note.body_length);
    AppendU16(out, note.reminder_length);
    AppendU16(out, note.order);
    AppendU64(out, note.reminder_unix_seconds);
    out->push_back(note.completed ? 1 : 0);
    out->push_back(note.delivered ? 1 : 0);
    AppendBytes(out, note.title.data(), note.title_length);
    AppendBytes(out, note.body.data(), note.body_length);
    AppendBytes(out, note.reminder.data(), note.reminder_length);
}

bool ReadNote(const uint8_t* data, size_t length, size_t* offset, NoteData* note) {
    if (!ReadU16(data, length, offset, &note->title_length) ||
        !ReadU16(data, length, offset, &note->body_length) ||
        !ReadU16(data, length, offset, &note->reminder_length) ||
        !ReadU16(data, length, offset, &note->order) ||
        !ReadU64(data, length, offset, &note->reminder_unix_seconds)) {
        return false;
    }
    if (*offset + 2 > length) return false;
    note->completed = data[(*offset)++] != 0;
    note->delivered = data[(*offset)++] != 0;
    return ReadBytes(data, length, offset, note->title.data(), kMaxTitleBytes,
                     note->title_length) &&
           ReadBytes(data, length, offset, note->body.data(), kMaxBodyBytes,
                     note->body_length) &&
           ReadBytes(data, length, offset, note->reminder.data(), kMaxReminderBytes,
                     note->reminder_length);
}

}  // namespace

uint32_t ComputeNoteCrc32(const uint8_t* data, size_t length) {
    uint32_t crc = 0xffffffffu;
    for (size_t index = 0; index < length; ++index) {
        crc ^= data[index];
        for (int bit = 0; bit < 8; ++bit) {
            crc = (crc >> 1) ^ (0xEDB88320u & (-(crc & 1u)));
        }
    }
    return crc ^ 0xffffffffu;
}

bool SetNoteText(NoteData* note, const std::string& title, const std::string& body,
                 const std::string& reminder) {
    if (note == nullptr || title.size() > kMaxTitleBytes || body.size() > kMaxBodyBytes ||
        reminder.size() > kMaxReminderBytes) {
        return false;
    }
    note->title.fill('\0');
    note->body.fill('\0');
    note->reminder.fill('\0');
    std::memcpy(note->title.data(), title.data(), title.size());
    std::memcpy(note->body.data(), body.data(), body.size());
    std::memcpy(note->reminder.data(), reminder.data(), reminder.size());
    note->title_length = static_cast<uint16_t>(title.size());
    note->body_length = static_cast<uint16_t>(body.size());
    note->reminder_length = static_cast<uint16_t>(reminder.size());
    return true;
}

std::vector<uint8_t> SerializeNoteSnapshot(const NoteSnapshot& snapshot) {
    if (snapshot.count > kMaxNotes) return {};
    for (size_t index = 0; index < snapshot.count; ++index) {
        const NoteData& note = snapshot.notes[index];
        if (note.title_length > kMaxTitleBytes || note.body_length > kMaxBodyBytes ||
            note.reminder_length > kMaxReminderBytes) return {};
    }
    const uint16_t count = snapshot.count;
    std::vector<uint8_t> payload;
    payload.reserve(32 + count * 32);
    AppendU16(&payload, static_cast<uint16_t>(snapshot.schema_version));
    AppendU64(&payload, snapshot.version);
    AppendU16(&payload, count);
    for (uint16_t index = 0; index < count; ++index) AppendNote(&payload, snapshot.notes[index]);
    const uint32_t crc = ComputeNoteCrc32(payload.data(), payload.size());
    payload.push_back(static_cast<uint8_t>(crc & 0xff));
    payload.push_back(static_cast<uint8_t>((crc >> 8) & 0xff));
    payload.push_back(static_cast<uint8_t>((crc >> 16) & 0xff));
    payload.push_back(static_cast<uint8_t>((crc >> 24) & 0xff));
    return payload;
}

bool DeserializeNoteSnapshot(const uint8_t* data, size_t length, NoteSnapshot* snapshot) {
    if (data == nullptr || snapshot == nullptr || length < 4) return false;
    const size_t payload_length = length - 4;
    const uint32_t expected = ComputeNoteCrc32(data, payload_length);
    const uint32_t actual = static_cast<uint32_t>(data[payload_length]) |
                            (static_cast<uint32_t>(data[payload_length + 1]) << 8) |
                            (static_cast<uint32_t>(data[payload_length + 2]) << 16) |
                            (static_cast<uint32_t>(data[payload_length + 3]) << 24);
    if (expected != actual) return false;
    size_t offset = 0;
    uint16_t schema = 0;
    if (!ReadU16(data, payload_length, &offset, &schema) || schema != kNoteSchemaVersion ||
        !ReadU64(data, payload_length, &offset, &snapshot->version) ||
        !ReadU16(data, payload_length, &offset, &snapshot->count) ||
        snapshot->count > kMaxNotes) return false;
    snapshot->schema_version = schema;
    snapshot->notes = {};
    for (uint16_t index = 0; index < snapshot->count; ++index) {
        if (!ReadNote(data, payload_length, &offset, &snapshot->notes[index])) return false;
    }
    return offset == payload_length;
}

NoteSnapshot MakeStarterNoteSnapshot() {
    NoteSnapshot snapshot;
    snapshot.version = kNoteDataVersion;
    snapshot.count = 1;
    SetNoteText(&snapshot.notes[0], "欢迎使用便利贴", "用手机编辑，设备离线时保留最后内容");
    snapshot.notes[0].order = 0;
    return snapshot;
}

}  // namespace gotim
