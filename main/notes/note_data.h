#pragma once

#include <array>
#include <cstddef>
#include <cstdint>
#include <string>
#include <vector>

namespace gotim {

constexpr size_t kMaxNotes = 20;
constexpr size_t kMaxTitleBytes = 48;
constexpr size_t kMaxBodyBytes = 384;
constexpr size_t kMaxReminderBytes = 32;
constexpr uint32_t kNoteSchemaVersion = 1;
constexpr uint64_t kNoteDataVersion = 1;

struct NoteData {
    std::array<char, kMaxTitleBytes + 1> title{};
    std::array<char, kMaxBodyBytes + 1> body{};
    std::array<char, kMaxReminderBytes + 1> reminder{};
    uint16_t title_length = 0;
    uint16_t body_length = 0;
    uint16_t reminder_length = 0;
    uint16_t order = 0;
    uint64_t reminder_unix_seconds = 0;
    bool completed = false;
    bool delivered = false;
};

struct NoteSnapshot {
    uint32_t schema_version = kNoteSchemaVersion;
    uint64_t version = kNoteDataVersion;
    uint16_t count = 0;
    std::array<NoteData, kMaxNotes> notes{};
};

bool SetNoteText(NoteData* note, const std::string& title, const std::string& body,
                 const std::string& reminder = "");
uint32_t ComputeNoteCrc32(const uint8_t* data, size_t length);
std::vector<uint8_t> SerializeNoteSnapshot(const NoteSnapshot& snapshot);
bool DeserializeNoteSnapshot(const uint8_t* data, size_t length, NoteSnapshot* snapshot);
void FillStarterNoteSnapshot(NoteSnapshot* snapshot);
NoteSnapshot MakeStarterNoteSnapshot();

}  // namespace gotim
