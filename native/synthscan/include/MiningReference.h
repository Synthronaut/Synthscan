#pragma once
#include <filesystem>
namespace SCMiner {
// Called on the application thread between scans. Existing loadout pointers
// remain stable; only validated numeric fields are replaced as one generation.
void refreshMiningReference(const std::filesystem::path& game);
bool miningReferenceSelfTest();
}
