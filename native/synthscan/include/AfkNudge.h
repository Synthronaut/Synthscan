#pragma once
#include <cstdint>
#include <random>

namespace SynthScan {
// No OS calls: the production adapter supplies observations; tests never move input.
class AfkNudge {
public:
    static constexpr std::uint64_t minInterval = 5 * 60 * 1000;
    static constexpr std::uint64_t maxInterval = 12 * 60 * 1000;
    using DelaySource = std::uint64_t (*)();
    explicit AfkNudge(DelaySource source = randomInterval) : delaySource_(source) {}
    std::uint64_t intervalMilliseconds() const { return wait_; }
    bool armed = false;
    unsigned nudges = 0;
    int nextInSeconds = -1;
    bool firstPulse() const { return first_; }
    const char* status = "off";
    void toggle(std::uint64_t now) {
        armed = !armed; since_ = now; focused_ = false; first_ = true; nextInSeconds = -1;
        if (armed) chooseInterval();
        status = armed ? "waiting for game" : "off";
    }
    bool due(std::uint64_t now, bool game, bool foreground, bool connected,
             bool inputValid, std::uint32_t idle, bool held) {
        nextInSeconds = -1;
        if (!armed) return false;
        if (!game) { armed = false; focused_ = false; status = "off (game closed)"; return false; }
        if (!foreground || !connected) {
            focused_ = false; since_ = now;
            status = foreground ? "waiting for session" : "paused (game in background)";
            return false;
        }
        if (!focused_) { focused_ = true; since_ = now; }
        if (!inputValid || held) {
            since_ = now; status = inputValid ? "paused (input held)" : "paused (input unavailable)";
            return false;
        }
        status = "waiting for inactivity";
        const auto wait = wait_;
        const auto focusWait = now - since_ < wait ? wait - (now - since_) : 0;
        const auto idleWait = idle < wait ? wait - idle : 0;
        const auto remaining = focusWait > idleWait ? focusWait : idleWait;
        nextInSeconds = int((remaining + 999) / 1000);
        return remaining == 0;
    }
    void sent(std::uint64_t now, bool success) {
        since_ = now;
        nextInSeconds = -1;
        if (success) { ++nudges; first_ = false; chooseInterval(); status = "pulse sent"; }
        else { armed = false; status = "error (input not sent)"; }
    }
    void interrupted(std::uint64_t now) {
        since_ = now; focused_ = false; nextInSeconds = -1; status = "pulse cancelled (input or focus changed)";
    }
private:
    static std::uint64_t randomInterval() {
        static thread_local std::mt19937_64 engine(std::random_device{}());
        return std::uniform_int_distribution<std::uint64_t>(minInterval, maxInterval)(engine);
    }
    void chooseInterval() {
        // One stable delay per wait, including the first; timer polling never redraws it.
        const auto value = delaySource_();
        wait_ = value < minInterval ? minInterval : value > maxInterval ? maxInterval : value;
    }
    DelaySource delaySource_;
    std::uint64_t wait_ = minInterval;
    std::uint64_t since_ = 0;
    bool focused_ = false;
    bool first_ = true;
};

// Separate events across frames instead of injecting a zero-net pair in one batch.
// Abort without a return movement if the player resumes input or changes focus.
class AfkMousePulse {
public:
    bool active = false;
    static constexpr unsigned count = 6;
    void start(std::uint64_t now, std::uint32_t lastInput) {
        nextAt_ = now; next_ = 0; baseline_ = lastInput; active = true;
    }
    void cancel() { active = false; }
    bool acceptsInput(std::uint32_t stamp) const {
        if (stamp == baseline_) return true;
        for (unsigned i = 0; i < next_; ++i) if (ownInput_[i] == stamp) return true;
        return false;
    }
    bool ready(std::uint64_t now) const {
        return active && next_ < count && now >= nextAt_;
    }
    int delta() const { return next_ < 3 ? 5 : -5; }
    void sent(std::uint64_t now, std::uint32_t stamp) {
        if (!active || next_ >= count) return;
        nextAt_ = now + delays_[next_];
        ownInput_[next_++] = stamp;
        if (next_ == count) active = false;
    }
private:
    std::uint64_t nextAt_ = 0;
    unsigned next_ = 0;
    std::uint32_t baseline_ = 0, ownInput_[count]{};
    static constexpr std::uint64_t delays_[count] = {40, 40, 120, 40, 40, 0};
};
}
