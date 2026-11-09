#pragma once
namespace SynthEdition {
#ifdef SYNTHSCAN_NO_SCREEN_READING
inline constexpr bool screenReading=false;
inline constexpr const char* name="standard";
#else
inline constexpr bool screenReading=true;
inline constexpr const char* name="full";
#endif
}
