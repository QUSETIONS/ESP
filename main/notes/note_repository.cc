#include "note_repository.h"

#include <nvs.h>

#include <algorithm>
#include <cstring>
#include <vector>

namespace gotim {
namespace {
constexpr char kNamespace[] = "gotim_notes";
constexpr char kStagingKey[] = "staging";
constexpr char kActiveKey[] = "active";
}

NoteRepository::NoteRepository() = default;

bool NoteRepository::ValidateSnapshot(const NoteSnapshot& snapshot) const {
    if (snapshot.schema_version != kNoteSchemaVersion || snapshot.count > kMaxNotes) return false;
    for (size_t index = 0; index < snapshot.count; ++index) {
        const NoteData& note = snapshot.notes[index];
        if (note.title_length > kMaxTitleBytes || note.body_length > kMaxBodyBytes ||
            note.reminder_length > kMaxReminderBytes) return false;
    }
    return true;
}

bool NoteRepository::ReadSnapshot(nvs_handle_t nvs, const char* key, NoteSnapshot* out) const {
    size_t size = 0;
    const bool staging = std::strcmp(key, kStagingKey) == 0;
    const esp_err_t size_error = staging
        ? nvs_get_blob(nvs, kStagingKey, nullptr, &size)
        : nvs_get_blob(nvs, key, nullptr, &size);
    if (size_error != ESP_OK || size == 0 || size > 16384) return false;
    std::vector<uint8_t> bytes(size);
    const esp_err_t read_error = staging
        ? nvs_get_blob(nvs, kStagingKey, bytes.data(), &size)
        : nvs_get_blob(nvs, key, bytes.data(), &size);
    if (read_error != ESP_OK) return false;
    return DeserializeNoteSnapshot(bytes.data(), size, out) && ValidateSnapshot(*out);
}

esp_err_t NoteRepository::Load(NoteSnapshot* out) {
    if (out == nullptr) return ESP_ERR_INVALID_ARG;
    nvs_handle_t nvs = 0;
    esp_err_t err = nvs_open(kNamespace, NVS_READWRITE, &nvs);
    if (err != ESP_OK) {
        snapshot_ = MakeStarterNoteSnapshot();
        *out = snapshot_;
        loaded_ = true;
        return err;
    }
    NoteSnapshot loaded;
    if (!ReadSnapshot(nvs, kActiveKey, &loaded) && !ReadSnapshot(nvs, kStagingKey, &loaded)) {
        loaded = MakeStarterNoteSnapshot();
    }
    nvs_close(nvs);
    snapshot_ = loaded;
    *out = snapshot_;
    loaded_ = true;
    return ESP_OK;
}

esp_err_t NoteRepository::Save(const NoteSnapshot& snapshot) {
    if (!ValidateSnapshot(snapshot)) return ESP_ERR_INVALID_ARG;
    const std::vector<uint8_t> bytes = SerializeNoteSnapshot(snapshot);
    nvs_handle_t nvs = 0;
    esp_err_t err = nvs_open(kNamespace, NVS_READWRITE, &nvs);
    if (err != ESP_OK) return err;
    err = nvs_set_blob(nvs, kStagingKey, bytes.data(), bytes.size());
    if (err == ESP_OK) err = nvs_commit(nvs);
    NoteSnapshot verified;
    if (err == ESP_OK && (!ReadSnapshot(nvs, kStagingKey, &verified) || verified.version != snapshot.version)) {
        err = ESP_ERR_INVALID_CRC;
    }
    if (err == ESP_OK) err = nvs_set_blob(nvs, kActiveKey, bytes.data(), bytes.size());
    if (err == ESP_OK) err = nvs_commit(nvs);
    nvs_close(nvs);
    if (err == ESP_OK) {
        snapshot_ = snapshot;
        loaded_ = true;
    }
    return err;
}

bool NoteRepository::ReplaceIfNewer(const NoteSnapshot& candidate) {
    if (!ValidateSnapshot(candidate) || candidate.version <= snapshot_.version) return false;
    return Save(candidate) == ESP_OK;
}

bool NoteRepository::ToggleComplete(size_t index) {
    if (index >= snapshot_.count) return false;
    NoteSnapshot candidate = snapshot_;
    NoteData& note = candidate.notes[index];
    note.completed = !note.completed;
    note.delivered = false;
    ++candidate.version;
    return Save(candidate) == ESP_OK;
}

bool NoteRepository::MarkDelivered(size_t index, uint64_t now_unix_seconds) {
    if (index >= snapshot_.count) return false;
    NoteSnapshot candidate = snapshot_;
    NoteData& note = candidate.notes[index];
    if (note.reminder_unix_seconds == 0 || note.reminder_unix_seconds > now_unix_seconds) return false;
    note.delivered = true;
    ++candidate.version;
    return Save(candidate) == ESP_OK;
}

bool NoteRepository::NextReminder(uint64_t now_unix_seconds, size_t* index,
                                  uint64_t* earliest_reminder) const {
    if (index == nullptr || earliest_reminder == nullptr) return false;
    *index = 0;
    *earliest_reminder = UINT64_MAX;
    bool found = false;
    for (size_t note_index = 0; note_index < snapshot_.count; ++note_index) {
        const NoteData& note = snapshot_.notes[note_index];
        if (!note.completed && !note.delivered && note.reminder_unix_seconds > now_unix_seconds &&
            note.reminder_unix_seconds < *earliest_reminder) {
            *earliest_reminder = note.reminder_unix_seconds;
            *index = note_index;
            found = true;
        }
    }
    return found;
}

}  // namespace gotim
