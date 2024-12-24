#include <random>
#include <iostream>
#include <vector>
#include <cmath>
#include <boost/asio.hpp>
#include <thread>
#include <atomic>
#include <chrono>
#include <deque>
#include <numeric>
#include "json.hpp"
#include <fstream>
#include "portaudio.h"
#ifdef _WIN32
#include <Windows.h>
#else
#include <unistd.h>
#endif

// Declare global variables
std::atomic<float> max_seen_volume(1.0f);
std::atomic<bool> is_drum_break_active(false);
std::atomic<bool> is_beat_active(false);
auto last_drum_break_time = std::chrono::steady_clock::now();
auto last_beat_time = std::chrono::steady_clock::now();
auto last_update_time = std::chrono::steady_clock::now();
std::ofstream log_file("wiz_vis_debug_log.txt"); // REMOVE BEFORE RELEASE

using boost::asio::ip::udp;
using json = nlohmann::json;

std::atomic<int> min_brightness(50); 
std::atomic<bool> running(true);
std::atomic<float> max_volume(0.0f);
std::atomic<float> prev_volume(0.0f); // Initialize prev_volume to 0
std::atomic<int> user_brightness(255);
std::atomic<float> drum_break_threshold(1.8f); // Default threshold value
std::atomic<size_t> drum_break_history_size(10); // Default history size value
std::atomic<float> beat_threshold(1.5f); // Default threshold factor
std::atomic<size_t> beat_history_size(5); // Default history size
std::atomic<int> color_cycle_duration_ms(300); // Default duration value
bool enable_interpolation = true;  // Default to false or adjust as needed
bool enable_smoothing = false;
bool enable_dynamic_brightness = false; 
bool reverse_colors = true;
bool random_reversal_interval = false;
bool enable_drum_break_detection = false; // Added for drum break detection
bool enable_beat_detection = false; // Added for beat detection
int DRUM_BREAK_INTERVAL_MS = 200; // Example value, adjust as needed
int reversal_interval = 5000;
int beat_index = 0; // Added for beat effect
std::mt19937 rng(std::chrono::steady_clock::now().time_since_epoch().count());
std::uniform_int_distribution<int> dist(3000, 10000);
auto last_reversal_time = std::chrono::steady_clock::now();
bool enable_debug_logging = false; // Set to true to enable logging to file

float upper_threshold = 0.05f;
float lower_threshold = 0.01f;

int UDP_PORT = 38899;             // Will be loaded from config
int FRAMES_PER_BUFFER = 256;      // Will be loaded from config
int NUM_CHANNELS = 2;             // Will be loaded from config
int MIN_UPDATE_INTERVAL_MS = 100; // Will be loaded from config
int userDeviceIndex = -1;         // will be loaded from config

std::string LIGHT_IP = "192.168.1.65"; // Will be loaded from config

std::vector<std::vector<int>> vivid_colors;
std::vector<std::vector<int>> beat_colors;
std::vector<std::vector<int>> drum_break_colors;

PaStream* stream;
std::vector<int16_t> audio_data;
std::vector<std::string> light_ips; // Add vector to store multiple light IPs

void log_debug(const std::string &message) {
    if (enable_debug_logging) {
        static std::ofstream log_file("wiz_vis_debug_log.txt", std::ios_base::app);
        log_file << message << std::endl;
    } else {
        // Optionally, print to console or do nothing
        std::cout << message << std::endl; // Remove this line if no output is needed
    }
}




void set_user_brightness(int brightness)
{
    if (brightness >= 0 && brightness <= 255)
    {
        user_brightness.store(brightness);
        log_file << "User brightness set to: " << brightness << std::endl;
    }
    else
    {
        log_file << "Invalid brightness value. Please set a value between 0 and 255." << std::endl;
    }
}



float calculate_initial_volume(const std::vector<int16_t> &audio_data)
{
    float volume = 0.0f;
    for (auto sample : audio_data)
        volume += sample * sample;
    volume = std::sqrt(volume / audio_data.size());

    if (audio_data.empty()) {
        std::cerr << "Error: Audio data is empty, cannot calculate initial volume." << std::endl;
    }

    return volume;
}


std::deque<float> volume_history; // History of volumes
const size_t history_size = 10; // Size of the moving average window

float smooth_volume(float current_volume)
{
    volume_history.push_back(current_volume);
    if (volume_history.size() > history_size)
    {
        volume_history.pop_front();
    }

    float smoothed_volume = 0.0f;
    for (float v : volume_history)
    {
        smoothed_volume += v;
    }
    smoothed_volume /= volume_history.size();
    
    return smoothed_volume;
}

float max_volume_seen = 1e4f; // Initialize max_volume_seen to a reasonable starting point

float process_audio(const std::vector<int16_t> &audio_data)
{
    float volume = calculate_initial_volume(audio_data);
    std::cout << "Initial Volume: " << volume << std::endl; // Debugging

    if (enable_smoothing)
    {
        volume = smooth_volume(volume);
        std::cout << "Smoothed Volume: " << volume << std::endl; // Debugging
    }

    if (std::isinf(volume) || std::isnan(volume))
    {
        volume = prev_volume; // Reset volume if it's invalid
        std::cerr << "Invalid Volume Detected and Corrected: " << volume << std::endl;
    }

    volume = std::pow(volume, 1.2f);
    std::cout << "Volume after Power Transformation: " << volume << std::endl; // Debugging

    if (!std::isinf(volume) && !std::isnan(volume))
    {
        prev_volume = volume;
    }
    else
    {
        std::cerr << "Invalid Volume Detected after Power Transformation: " << volume << std::endl;
    }

    if (volume > max_volume + upper_threshold)
    {
        max_volume = volume;
    }
    else if (volume < max_volume - lower_threshold)
    {
        max_volume = std::max(max_volume - lower_threshold, 0.0f);
    }

    std::cout << "Processed Audio Volume: " << volume << std::endl;
    return volume;
}

std::vector<int> vivid_interpolate_color(const std::vector<int> &color1, const std::vector<int> &color2, float factor, bool interpolationEnabled)
{
    std::vector<int> color(3);

    if (!interpolationEnabled) {
        // If interpolation is disabled, return color1 directly
        std::cout << "Interpolation disabled, returning color1: "
                  << "R: " << color1[0] 
                  << " G: " << color1[1] 
                  << " B: " << color1[2] << std::endl;
        return color1;
    }

    for (int i = 0; i < 3; ++i)
    {
        float blend = std::sqrt(factor);
        color[i] = static_cast<int>((1 - blend) * color1[i] + blend * color2[i]);
    }

    std::cout << "Interpolation enabled, interpolated color: "
              << "R: " << color[0] 
              << " G: " << color[1] 
              << " B: " << color[2] << std::endl;

    return color;
}

std::vector<int> get_vivid_color_from_volume(float volume)
{
    float normalized_volume = volume / max_volume;

    auto now = std::chrono::steady_clock::now();
    auto elapsed_time = std::chrono::duration_cast<std::chrono::milliseconds>(now - last_reversal_time);
    if (elapsed_time.count() >= reversal_interval)
    {
        reverse_colors = !reverse_colors;
        last_reversal_time = now;
        if (random_reversal_interval)
            reversal_interval = dist(rng);
    }
    if (reverse_colors)
        std::reverse(vivid_colors.begin(), vivid_colors.end());

    int num_ranges = vivid_colors.size() - 1;
    float section = 1.0f / num_ranges;
    int idx = std::min(static_cast<int>(normalized_volume / section), num_ranges - 1);
    float factor = (normalized_volume - idx * section) / section;

    int start_idx = idx % vivid_colors.size();
    int end_idx = (start_idx + 1) % vivid_colors.size();
    
    std::vector<int> vivid_color = vivid_interpolate_color(vivid_colors[start_idx], vivid_colors[end_idx], factor, enable_interpolation);

    std::cout << "Volume: " << volume 
              << ", Normalized Volume: " << normalized_volume 
              << ", Vivid Color: R: " << vivid_color[0] 
              << " G: " << vivid_color[1] 
              << " B: " << vivid_color[2] << std::endl;

    return vivid_color;
}
void send_udp_command(const std::vector<int> &color, int volume)
{
    try
    {
        boost::asio::io_context io_context;
        udp::socket socket(io_context, udp::endpoint(udp::v4(), 0));
        udp::resolver resolver(io_context);

        for (const auto &ip : light_ips)
        {
            udp::endpoint receiver_endpoint = *resolver.resolve(udp::v4(), ip, std::to_string(UDP_PORT)).begin();

            json payload;
            payload["method"] = "setPilot";
            payload["params"]["r"] = color[0];
            payload["params"]["g"] = color[1];
            payload["params"]["b"] = color[2];
            payload["params"]["dimming"] = volume;

            std::string message = payload.dump();
            socket.send_to(boost::asio::buffer(message), receiver_endpoint);
        }
    }
    catch (std::exception &e)
    {
        std::cerr << "Error sending UDP command: " << e.what() << std::endl;
    }
}


// Define a custom clamp function
template <typename T>
T clamp(const T& value, const T& min, const T& max) {
    if (value < min)
        return min;
    else if (value > max)
        return max;
    else
        return value;
}

void load_config(const std::string &config_path)
{
    std::ifstream config_file(config_path);
    if (!config_file)
    {
        std::cerr << "Could not open config file: " << config_path << std::endl;
        return;
    }

    std::cout << "Config file opened successfully: " << config_path << std::endl;

    json config;
    config_file >> config;

    std::cout << "Config file content: " << config.dump(4) << std::endl; // Print the whole config file

    try
    {
        // User Device Input
        if (config.contains("audio") && config["audio"].contains("device_index")) {
            userDeviceIndex = config["audio"]["device_index"].get<int>();
            std::cout << "Loaded audio device_index: " << userDeviceIndex << std::endl;
        } else {
            std::cerr << "Audio device index not found in config file. Defaulting to -1." << std::endl;
        }
        // Minimum Brightness setting
        if (config["brightness"].contains("min_brightness")) {
            min_brightness = config["brightness"]["min_brightness"].get<int>();
            std::cout << "Loaded min_brightness: " << min_brightness << std::endl;
        }

        // Load brightness settings
        if (config["brightness"].contains("user_brightness")) {
            user_brightness = config["brightness"]["user_brightness"].get<int>();
            std::cout << "Loaded user_brightness: " << user_brightness << std::endl;
        }

        if (config["brightness"].contains("enable_dynamic_brightness")) {
            enable_dynamic_brightness = config["brightness"]["enable_dynamic_brightness"].get<bool>();
            std::cout << "Loaded enable_dynamic_brightness: " << enable_dynamic_brightness << std::endl;
        }

        // Load visualization settings
        if (config["visualization"].contains("upper_threshold")) {
            upper_threshold = config["visualization"]["upper_threshold"].get<float>();
            std::cout << "Loaded upper_threshold: " << upper_threshold << std::endl;
        }
        if (config["visualization"].contains("lower_threshold")) {
            lower_threshold = config["visualization"]["lower_threshold"].get<float>();
            std::cout << "Loaded lower_threshold: " << lower_threshold << std::endl;
        }
        if (config["visualization"].contains("min_update_interval_ms")) {
            MIN_UPDATE_INTERVAL_MS = config["visualization"]["min_update_interval_ms"].get<int>();
            std::cout << "Loaded min_update_interval_ms: " << MIN_UPDATE_INTERVAL_MS << std::endl;
        }
        if (config["visualization"].contains("drum_break_threshold")) {
            drum_break_threshold = config["visualization"]["drum_break_threshold"].get<float>();
            std::cout << "Loaded drum_break_threshold: " << drum_break_threshold << std::endl;
        }
        if (config["visualization"].contains("drum_break_history_size")) {
            drum_break_history_size = config["visualization"]["drum_break_history_size"].get<size_t>();
            std::cout << "Loaded drum_break_history_size: " << drum_break_history_size << std::endl;
        }
        if (config["visualization"].contains("beat_threshold")) {
            beat_threshold = config["visualization"]["beat_threshold"].get<float>();
            std::cout << "Loaded beat_threshold: " << beat_threshold << std::endl;
        }
        if (config["visualization"].contains("beat_history_size")) {
            beat_history_size = config["visualization"]["beat_history_size"].get<size_t>();
            std::cout << "Loaded beat_history_size: " << beat_history_size << std::endl;
        }

        // Load network settings
        if (config["network"].contains("udp_port")) {
            UDP_PORT = config["network"]["udp_port"].get<int>();
            std::cout << "Loaded udp_port: " << UDP_PORT << std::endl;
        }

        // Ensure light_ips is a list, if it's not, initialize it as an empty array
        auto light_ips_json = config["network"].value("light_ips", json::array());
        light_ips.clear();
        for (const auto &ip : light_ips_json)
        {
            if (ip.is_string()) {
                light_ips.push_back(ip.get<std::string>());
                std::cout << "Loaded light IP: " << ip.get<std::string>() << std::endl;
            }
        }

        // Load feature settings
        if (config["features"].contains("enable_smoothing")) {
            enable_smoothing = config["features"]["enable_smoothing"].get<bool>();
            std::cout << "Loaded enable_smoothing: " << enable_smoothing << std::endl;
        }
        if (config["features"].contains("reverse_colors")) {
            reverse_colors = config["features"]["reverse_colors"].get<bool>();
            std::cout << "Loaded reverse_colors: " << reverse_colors << std::endl;
        }
        if (config["features"].contains("random_reversal_interval")) {
            random_reversal_interval = config["features"]["random_reversal_interval"].get<bool>();
            std::cout << "Loaded random_reversal_interval: " << random_reversal_interval << std::endl;
        }
        if (config["features"].contains("reversal_interval")) {
            reversal_interval = config["features"]["reversal_interval"].get<int>();
            std::cout << "Loaded reversal_interval: " << reversal_interval << std::endl;
        }
        if (config["features"].contains("enable_interpolation")) {
            enable_interpolation = config["features"]["enable_interpolation"].get<bool>();
            std::cout << "Loaded enable_interpolation: " << enable_interpolation << std::endl;
        }

        if (config["features"].contains("enable_drum_break_detection")) {
            enable_drum_break_detection = config["features"]["enable_drum_break_detection"].get<bool>();
            std::cout << "Loaded enable_drum_break_detection: " << enable_drum_break_detection << std::endl;
        }
        if (config["features"].contains("enable_beat_detection")) {
            enable_beat_detection = config["features"]["enable_beat_detection"].get<bool>();
            std::cout << "Loaded enable_beat_detection: " << enable_beat_detection << std::endl;
        }

        // Load color settings
        if (config["color_settings"].contains("vivid_colors"))
        {
            vivid_colors.clear();
            for (const auto &color : config["color_settings"]["vivid_colors"])
            {
                vivid_colors.push_back({color[0].get<int>(), color[1].get<int>(), color[2].get<int>()});
                std::cout << "Loaded vivid_color: [" << color[0].get<int>() << ", " << color[1].get<int>() << ", " << color[2].get<int>() << "]" << std::endl;
            }
        }

        if (config["color_settings"].contains("beat_colors"))
        {
            beat_colors.clear();
            for (const auto &color : config["color_settings"]["beat_colors"])
            {
                beat_colors.push_back({color[0].get<int>(), color[1].get<int>(), color[2].get<int>()});
                std::cout << "Loaded beat_color: [" << color[0].get<int>() << ", " << color[1].get<int>() << ", " << color[2].get<int>() << "]" << std::endl;
            }
        }

        if (config["color_settings"].contains("drum_break_colors"))
        {
            drum_break_colors.clear();
            for (const auto &color : config["color_settings"]["drum_break_colors"])
            {
                drum_break_colors.push_back({color[0].get<int>(), color[1].get<int>(), color[2].get<int>()});
                std::cout << "Loaded drum_break_color: [" << color[0].get<int>() << ", " << color[1].get<int>() << ", " << color[2].get<int>() << "]" << std::endl;
            }
        }
    }
    catch (const json::exception &e)
    {
        std::cerr << "Error parsing config file: " << e.what() << std::endl;
    }
}


bool detect_drum_break(float volume)
{
    static std::deque<float> volume_history;
    static auto last_drum_break_time = std::chrono::steady_clock::now();

    volume_history.push_back(volume);
    if (volume_history.size() > drum_break_history_size)
    {
        volume_history.pop_front();
    }

    float avg_volume = std::accumulate(volume_history.begin(), volume_history.end(), 0.0f) / volume_history.size();
    float threshold = avg_volume * drum_break_threshold; // Use global variable for threshold

    auto now = std::chrono::steady_clock::now();
    auto elapsed_time = std::chrono::duration_cast<std::chrono::milliseconds>(now - last_drum_break_time);

    std::cout << "Volume: " << volume << ", Avg Volume: " << avg_volume << ", Drum Break Threshold: " << threshold << ", Elapsed Time: " << elapsed_time.count() << " ms" << std::endl;

    if (volume > threshold && elapsed_time.count() > DRUM_BREAK_INTERVAL_MS)
    {
        last_drum_break_time = now;
        std::cout << "Drum break detected, triggering intense visual effect!" << std::endl;
        return true;
    }

    return false;
}

bool detect_beat(float volume)
{
    static std::deque<float> volume_history;
    static auto last_beat_time = std::chrono::steady_clock::now();

    volume_history.push_back(volume);
    if (volume_history.size() > beat_history_size)
    {
        volume_history.pop_front();
    }

    float avg_volume = std::accumulate(volume_history.begin(), volume_history.end(), 0.0f) / volume_history.size();
    float threshold = avg_volume * beat_threshold; // Use global variable for threshold

    auto now = std::chrono::steady_clock::now();
    auto elapsed_time = std::chrono::duration_cast<std::chrono::milliseconds>(now - last_beat_time);

    std::cout << "Volume: " << volume << ", Avg Volume: " << avg_volume << ", Threshold: " << threshold << ", Elapsed Time: " << elapsed_time.count() << " ms" << std::endl;

    if (volume > threshold && elapsed_time.count() > color_cycle_duration_ms)
    {
        last_beat_time = now;
        std::cout << "BEAT DETECTED, applying colors!" << std::endl;
        return true;
    }

    return false;
}


// Callback function for PortAudio
static int audio_callback(const void* inputBuffer, void* outputBuffer,
    unsigned long framesPerBuffer, const PaStreamCallbackTimeInfo* timeInfo,
    PaStreamCallbackFlags statusFlags, void* userData) {

    std::cout << "Callback started..." << std::endl;

    // Check if input buffer is null
    if (inputBuffer == nullptr) {
        std::cerr << "Input buffer is null. Skipping processing." << std::endl;
        return paContinue;
    }

    // Convert input buffer to audio data
    const float* in = (const float*)inputBuffer;
    audio_data.resize(framesPerBuffer * NUM_CHANNELS);

    // Check for silence in the input buffer
    bool is_silent = true;
    for (unsigned int i = 0; i < framesPerBuffer * NUM_CHANNELS; i++) {
        audio_data[i] = static_cast<int16_t>(in[i] * 32767.0f);
        if (audio_data[i] != 0) {
            is_silent = false;  // Detected non-zero data
        }
    }

    if (is_silent) {
        std::cout << "Silence detected. Skipping processing." << std::endl;
        return paContinue;  // Skip further processing
    }

    // Calculate volume
    float volume = process_audio(audio_data);

    // Silence threshold check
    const float silence_threshold = 0.01f;  // Adjust as needed
    if (volume < silence_threshold) {
        std::cout << "Volume below threshold (" << volume << "). Skipping processing." << std::endl;
        return paContinue;
    }

    // Process vivid color and brightness
    std::vector<int> color = get_vivid_color_from_volume(volume);
    int brightness = user_brightness.load();

    if (enable_dynamic_brightness) {
        float normalized_volume = clamp(volume / max_seen_volume, 0.0f, 1.0f);
        brightness = static_cast<int>(std::pow(normalized_volume, 1.5f) * user_brightness.load());
        brightness = std::max(brightness, min_brightness.load());
    }

    brightness = clamp(brightness, min_brightness.load(), 255);

    // Drum break detection
    bool drum_break_detected = enable_drum_break_detection && detect_drum_break(volume);
    if (drum_break_detected) {
        is_drum_break_active = true;
        last_drum_break_time = std::chrono::steady_clock::now();
    }

    if (is_drum_break_active) {
        auto now = std::chrono::steady_clock::now();
        auto drum_break_elapsed = std::chrono::duration_cast<std::chrono::milliseconds>(now - last_drum_break_time);
        if (drum_break_elapsed.count() < DRUM_BREAK_INTERVAL_MS) {
            color = drum_break_colors[(drum_break_elapsed.count() / 50) % drum_break_colors.size()];
            brightness = 255;
        } else {
            is_drum_break_active = false;
        }
    }

    // Beat detection
    bool beat_detected = !is_drum_break_active && enable_beat_detection && detect_beat(volume);
    if (beat_detected) {
        is_beat_active = true;
        last_beat_time = std::chrono::steady_clock::now();
        beat_index = 0;
    }

    if (is_beat_active) {
        auto now = std::chrono::steady_clock::now();
        auto beat_elapsed = std::chrono::duration_cast<std::chrono::milliseconds>(now - last_beat_time);
        if (beat_elapsed.count() < 1000) {
            color = beat_colors[beat_index % beat_colors.size()];
            beat_index++;
        } else {
            is_beat_active = false;
        }
    }

    // Update lights if minimum interval has passed
    auto now = std::chrono::steady_clock::now();
    auto elapsed_time = std::chrono::duration_cast<std::chrono::milliseconds>(now - last_update_time);

    if (elapsed_time.count() >= MIN_UPDATE_INTERVAL_MS) {
        send_udp_command(color, brightness);
        last_update_time = now;
    }

    std::cout << "Callback completed..." << std::endl;

    return paContinue;
}


void audio_processing_loop(const std::string& light_ip) {
    PaError err;

    log_debug("Starting audio_processing_loop...");
    std::cout << "Initializing PortAudio..." << std::endl;
    log_debug("Initializing PortAudio...");

    int deviceIndex = -1; // Initialize with an invalid index

    // Load the device index from the config file
    std::ifstream config_file("volume_config.json");
    if (config_file) {
        json config;
        config_file >> config;
        if (config.contains("audio") && config["audio"].contains("device_index")) {
            deviceIndex = config["audio"]["device_index"].get<int>();
        }
    }

    // Function to initialize the PortAudio stream
    auto initialize_stream = [&]() -> bool {
        err = Pa_Initialize();
        if (err != paNoError) {
            log_debug("Fatal error Initializing PortAudio.");
            std::cerr << "PortAudio initialization error: " << Pa_GetErrorText(err) << std::endl;
            return false;
        }

        if (deviceIndex < 0 || deviceIndex >= Pa_GetDeviceCount()) {
            std::cerr << "Invalid device index from config. Please check your configuration." << std::endl;
            log_debug("Invalid device index from config. Please check your configuration.");
            return false;
        }

        const PaDeviceInfo* deviceInfo = Pa_GetDeviceInfo(deviceIndex);
        if (deviceInfo == nullptr) {
            log_debug("Unable to retrieve device info for device index " + std::to_string(deviceIndex) + ".");
            std::cerr << "Unable to retrieve device info for device index " << deviceIndex << "." << std::endl;
            Pa_Terminate();
            return false;
        }

        std::cout << "Using audio device: " << deviceInfo->name << std::endl;
        log_debug("Using audio device: " + std::string(deviceInfo->name));

        PaStreamParameters inputParameters;
        inputParameters.device = deviceIndex;
        inputParameters.channelCount = NUM_CHANNELS;
        inputParameters.sampleFormat = paFloat32;
        inputParameters.suggestedLatency = deviceInfo->defaultLowInputLatency;
        inputParameters.hostApiSpecificStreamInfo = nullptr;

        std::cout << "Opening audio stream..." << std::endl;
        log_debug("Opening audio stream...");
        err = Pa_OpenStream(&stream, &inputParameters, NULL, 48000, FRAMES_PER_BUFFER, paClipOff, audio_callback, NULL);
        if (err != paNoError) {
            std::string error_msg = "PortAudio open stream error: " + std::string(Pa_GetErrorText(err));
            log_debug(error_msg);
            std::cerr << error_msg << std::endl;
            Pa_Terminate();
            return false;
        }

        std::cout << "Starting audio stream..." << std::endl;
        log_debug("Starting audio stream...");
        err = Pa_StartStream(stream);
        if (err != paNoError) {
            std::string error_msg = "PortAudio start stream error: " + std::string(Pa_GetErrorText(err));
            log_debug(error_msg);
            std::cerr << error_msg << std::endl;
            Pa_CloseStream(stream);
            Pa_Terminate();
            return false;
        }

        return true;
    };

    if (!initialize_stream()) {
        return;
    }

    log_debug("Processing audio... Press Ctrl+C to stop.");
    std::cout << "Processing audio... Press Ctrl+C to stop." << std::endl;

    // Main loop to keep the program running
    while (running) {
        log_debug("Main loop iteration...");

        if (!Pa_IsStreamActive(stream)) {
            log_debug("Stream is inactive. Reinitializing...");
            std::cerr << "Stream is inactive. Reinitializing..." << std::endl;

            Pa_CloseStream(stream);
            Pa_Terminate();

            if (!initialize_stream()) {
                return;
            }
        }

        std::this_thread::sleep_for(std::chrono::milliseconds(100));
    }

    std::cout << "Stopping audio stream..." << std::endl;
    log_debug("Stopping audio stream...");
    err = Pa_StopStream(stream);
    if (err != paNoError) {
        std::string error_msg = "PortAudio stop stream error: " + std::string(Pa_GetErrorText(err));
        log_debug(error_msg);
        std::cerr << error_msg << std::endl;
    }

    std::cout << "Closing audio stream..." << std::endl;
    log_debug("Closing audio stream...");
    err = Pa_CloseStream(stream);
    if (err != paNoError) {
        std::string error_msg = "PortAudio close stream error: " + std::string(Pa_GetErrorText(err));
        log_debug(error_msg);
        std::cerr << error_msg << std::endl;
    }

    std::cout << "Terminating PortAudio..." << std::endl;
    log_debug("Terminating PortAudio...");
    Pa_Terminate();
}




int main(int argc, char* argv[]) {
    log_debug("Starting main function...");
    
    std::string config_file_path;

    #ifdef _WIN32
    // For Windows systems
    char path[MAX_PATH];
    if (GetModuleFileNameA(NULL, path, MAX_PATH) != 0) {
        std::string::size_type pos = std::string(path).find_last_of("\\/");
        config_file_path = std::string(path).substr(0, pos) + "\\volume_config.json";
    } else {
        std::cerr << "Error getting executable path. Using default config path." << std::endl;
        config_file_path = "volume_config.json";
    }
    #else
    // For Unix-like systems
    char path[1024];
    ssize_t count = readlink("/proc/self/exe", path, sizeof(path));
    if (count != -1) {
        std::string::size_type pos = std::string(path).find_last_of("\\/");
        config_file_path = std::string(path).substr(0, pos) + "/volume_config.json";
    } else {
        std::cerr << "Error getting executable path. Using default config path." << std::endl;
        config_file_path = "volume_config.json";
    }
    #endif

    if (argc >= 2) {
        config_file_path = argv[1];
    } else {
        log_debug("Using default config file path: " + config_file_path);
    }

    log_debug("Config file path: " + config_file_path);

    load_config(config_file_path);
    log_debug("Config loaded successfully.");

    std::thread audio_thread(audio_processing_loop, LIGHT_IP);
    log_debug("Audio thread started.");
    audio_thread.join();
    log_debug("Audio thread joined.");

    return 0;
}




