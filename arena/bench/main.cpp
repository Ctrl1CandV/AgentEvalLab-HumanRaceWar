// Fixed, single-thread integer workload. Runs and compiles only inside bwrap.
#include <cstdint>
#include <ctime>
#include <iostream>
#include <string>

static std::uint64_t cpu_ns() {
    timespec t{};
    if (clock_gettime(CLOCK_PROCESS_CPUTIME_ID, &t) != 0) std::terminate();
    return std::uint64_t(t.tv_sec) * 1000000000ULL + t.tv_nsec;
}
int main() {
    std::string command;
    if (!std::getline(std::cin, command) || command != "BENCH") return 2;
    std::cout << "READY\n" << std::flush;
    if (!std::getline(std::cin, command) || command != "GO") return 3;
    auto start = cpu_ns();
    std::uint64_t value = 0x9e3779b97f4a7c15ULL;
    for (std::uint64_t i = 0; i < 80000000ULL; ++i) {
        value ^= value >> 12;
        value ^= value << 25;
        value ^= value >> 27;
        value *= 0x2545f4914f6cdd1dULL;
    }
    auto elapsed = cpu_ns() - start;
    std::cout << "BENCH " << elapsed << ' ' << value << "\nEND\n" << std::flush;
    // Keep the process alive until the harness has sampled its CPU clock.
    std::getline(std::cin, command);
}
