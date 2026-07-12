#pragma once

#include "note_data.h"

#include <esp_err.h>
#include <nvs.h>

#include <cstddef>
#include <cstdint>

namespace gotim {

class NoteRepository {
public:
    NoteRepository();

    esp_err_t Load(NoteSnapshot* out);
    esp_err_t Save(const NoteSnapshot& snapshot);
    bool ReplaceIfNewer(const NoteSnapshot& candidate);
    bool ToggleComplete(size_t index);
    bool MarkDelivered(size_t index, uint64_t now_unix_seconds);
    bool NextReminder(uint64_t now_unix_seconds, size_t* index,
                      uint64_t* earliest_reminder) const;
    const NoteSnapshot& snapshot() const { return snapshot_; }

private:
    bool ValidateSnapshot(const NoteSnapshot& snapshot) const;
    bool ReadSnapshot(nvs_handle_t nvs, const char* key, NoteSnapshot* out) const;
    NoteSnapshot snapshot_ = MakeStarterNoteSnapshot();
    bool loaded_ = false;
};

}  // namespace gotim
