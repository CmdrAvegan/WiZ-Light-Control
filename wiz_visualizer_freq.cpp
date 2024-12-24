#include <iostream>
#include <vector>
#include <cmath>
#include <portaudio.h>
#include <fftw3.h>
#include <atomic>
#include <boost/asio.hpp>
#include <thread>
#include <chrono>
#include "nlohmann/json.hpp"
#include <fstream> // For file handling
#include <string>  // For std::string
#include <random>  // For std::mt19937 and std::uniform_int_distribution
#include <iostream>

// Add these variables at the top of your script or in a suitable scope
static fftw_complex* fft_output = nullptr;  // Pointer for FFTW output
static std::vector<double> fft_input;      // FFTW input buffer
static int fft_size;                       // FFT size
static fftw_plan fft_plan = nullptr; // Global FFTW plan
static boost::asio::io_context global_io_context;
static boost::asio::ip::udp::socket udp_socket(global_io_context, boost::asio::ip::udp::endpoint(boost::asio::ip::udp::v4(), 0));
// Flag to track FFT initialization status
static bool fft_initialized = false;



std::mt19937 rng(std::chrono::steady_clock::now().time_since_epoch().count());
std::uniform_int_distribution<int> dist(3000, 10000);
auto last_reversal_time = std::chrono::steady_clock::now();
int reversal_interval;
bool reverse_colors;
bool random_reversal_interval;
bool enable_interpolation;

using json = nlohmann::json;

template <typename T>
T clamp(const T& value, const T& min_value, const T& max_value) {
    return std::max(min_value, std::min(value, max_value));
}

// Rename the newer clamp function
template <typename T>
T bounded_value(T value, T min, T max) {
    if (value < min) return min;
    if (value > max) return max;
    return value;
}

void auto_calibrate_silence_threshold(const std::vector<int16_t>& audio_data, int SAMPLE_RATE, float& silence_threshold, int duration_seconds) {
    std::cout << "Starting silence threshold calibration for " << duration_seconds << " seconds..." << std::endl;

    float total_volume = 0.0f;
    int count = 0;

    // Simulate processing the audio data for the given duration
    for (int i = 0; i < SAMPLE_RATE * duration_seconds && i < audio_data.size(); ++i) {
        total_volume += audio_data[i] * audio_data[i];
        count++;

        // Simulate work over time (sleep for 1 second per iteration)
        if (i % SAMPLE_RATE == 0) {
            std::this_thread::sleep_for(std::chrono::seconds(1));  // Simulate 1 second of work
            std::cout << "Calibration in progress: " << (i / SAMPLE_RATE) + 1 << " seconds..." << std::endl;
        }
    }

    // Calculate RMS and add a margin
    silence_threshold = std::sqrt(total_volume / count) * 1.1f; // Add a 10% margin
    std::cout << "Calibrated Silence Threshold: " << silence_threshold << std::endl;

    // Optionally, update the config.json with the new threshold
    std::ifstream config_file("config.json");
    if (!config_file.is_open()) {
        std::cerr << "Could not open config.json for reading." << std::endl;
        return;
    }

    json config_json;
    try {
        config_file >> config_json;
    } catch (const json::parse_error& e) {
        std::cerr << "JSON parse error: " << e.what() << std::endl;
        return;
    }
    config_file.close();

    config_json["advanced_settings"]["silence_threshold"] = silence_threshold;

    std::ofstream updated_config("config.json", std::ios::trunc);
    if (updated_config.is_open()) {
        updated_config << config_json.dump(4); // Write JSON with indentation
        updated_config.close();
    } else {
        std::cerr << "Could not open config.json for writing." << std::endl;
    }
}

int calculate_brightness(float energy, float max_energy) {
    int min_brightness = 50; // Prevent lights from being too dim
    return clamp(static_cast<int>(min_brightness + (energy / max_energy) * (255 - min_brightness)), min_brightness, 255);
}
using boost::asio::ip::udp;

int SAMPLE_RATE = 44100;
int FRAMES_PER_BUFFER = 1024;
int NUM_CHANNELS = 2;
int UDP_PORT = 12345;
int MIN_UPDATE_INTERVAL_MS = 100;
float FREQUENCY_SENSITIVITY_THRESHOLD = 0.01f; // low = less sensitive to freq, high = more sensitive
float dynamic_threshold;
int target_brightness = 255;
int current_brightness = 255;
bool enable_beat_detection = true;
int hysteresis_counter = 0;
size_t recent_energies_size = 10;
float sensitivity_multiplier = 1.0f;
int brightness_multiplier = 5;
int off_effect_delay_ms = 100;
bool gradual_brightness_recovery = true;
bool enable_silence_threshold = true; // Default to enabled
float silence_threshold = 0.02f;       // Default threshold
bool apply_smooth_transition = false; // Set this to true or false to enable/disable smooth color transition
bool effects_enabled = false;
float target_volume = 10000.0f; // Target RMS volume

std::atomic<bool> running(true);
std::atomic<float> max_frequency(0.0f);
std::atomic<float> prev_frequency(0.0f);
std::string audio_device; // Add this global declaration

enum LightEffect {
    CHANGE_COLOR,
    ADJUST_BRIGHTNESS,
    TURN_OFF_ON
};



     // CONFIGURATION       // CONFIGURATION



struct LightConfig {
    std::string ip;
    LightEffect effect;
    std::vector<std::vector<int>> colors; // List of colors for each light
};

std::vector<LightConfig> light_configs;

std::vector<LightConfig> load_configuration(const std::string& file_path, std::string& audio_device) {
    std::ifstream config_file(file_path);
    if (!config_file) {
        std::cerr << "Unable to open config file: " << file_path << std::endl;
        return {};
    }

    json config_json;
    config_file >> config_json;

    // General settings
    audio_device = config_json["audio_device"].get<std::string>();

    // Advanced settings
    SAMPLE_RATE = config_json["advanced_settings"]["SAMPLE_RATE"].get<int>();
    FRAMES_PER_BUFFER = config_json["advanced_settings"]["FRAMES_PER_BUFFER"].get<int>();
    NUM_CHANNELS = config_json["advanced_settings"]["NUM_CHANNELS"].get<int>();
    UDP_PORT = config_json["advanced_settings"]["UDP_PORT"].get<int>();
    MIN_UPDATE_INTERVAL_MS = config_json["advanced_settings"]["MIN_UPDATE_INTERVAL_MS"].get<int>();
    FREQUENCY_SENSITIVITY_THRESHOLD = config_json["advanced_settings"]["FREQUENCY_SENSITIVITY_THRESHOLD"].get<float>();
    dynamic_threshold = config_json["advanced_settings"]["dynamic_threshold"].get<float>();
    target_brightness = config_json["advanced_settings"]["target_brightness"].get<int>();
    current_brightness = config_json["advanced_settings"]["current_brightness"].get<int>();
    hysteresis_counter = config_json["advanced_settings"]["hysteresis_counter"].get<int>();
    recent_energies_size = config_json["advanced_settings"]["recent_energies_size"].get<int>();
    sensitivity_multiplier = config_json["advanced_settings"]["sensitivity_multiplier"].get<float>();
    brightness_multiplier = config_json["advanced_settings"]["brightness_multiplier"].get<int>();
    off_effect_delay_ms = config_json["advanced_settings"]["off_effect_delay_ms"].get<int>();
    gradual_brightness_recovery = config_json["advanced_settings"]["gradual_brightness_recovery"].get<bool>();
    enable_silence_threshold = config_json["advanced_settings"].value("enable_silence_threshold", true);
    silence_threshold = config_json["advanced_settings"].value("silence_threshold", 0.02f);
    apply_smooth_transition = config_json["advanced_settings"]["apply_smooth_transition"].get<bool>();
    prev_frequency = config_json["advanced_settings"]["prev_frequency"].get<float>();
    effects_enabled = config_json["advanced_settings"]["effects_enabled"].get<bool>();
    target_volume = config_json["advanced_settings"].value("target_volume", 1000.00f);

    // Load light configurations
    std::vector<LightConfig> light_configs;
    for (const auto& light : config_json["lights"]) {
        LightEffect effect;
        if (light["effect"] == "CHANGE_COLOR") {
            effect = CHANGE_COLOR;
        } else if (light["effect"] == "ADJUST_BRIGHTNESS") {
            effect = ADJUST_BRIGHTNESS;
        } else if (light["effect"] == "TURN_OFF_ON") {
            effect = TURN_OFF_ON;
        }

        std::vector<std::vector<int>> colors = light["colors"].get<std::vector<std::vector<int>>>();
        light_configs.push_back({ light["ip"], effect, colors });
    }

    return light_configs;
}


    // COLOR FUNCTIONS      // COLOR FUNCTIONS



std::vector<int> smooth_color_transition(const std::vector<int>& current, const std::vector<int>& target, float factor) {
    std::vector<int> blended_color(3);
    for (int i = 0; i < 3; ++i) {
        blended_color[i] = static_cast<int>(current[i] + factor * (target[i] - current[i]));
    }
    return blended_color;
}

std::vector<int> map_frequency_to_color(float frequency, const std::vector<std::vector<int>>& colors, float sample_rate) {
    float max_frequency = sample_rate / 2.0; // Nyquist limit
    int num_colors = colors.size();
    float range_size = max_frequency / num_colors;

    // Determine the range
    int range_index = std::min(static_cast<int>(frequency / range_size), num_colors - 1);

    // Debugging: Log frequency and selected range
    std::cout << "Frequency: " << frequency << ", Range Index: " << range_index << std::endl;

    return colors[range_index];
}


std::vector<int> vivid_interpolate_color(const std::vector<int>& color1, const std::vector<int>& color2, float factor) {
    std::vector<int> color(3);
    for (int i = 0; i < 3; ++i) {
        color[i] = static_cast<int>(color1[i] + (color2[i] - color1[i]) * factor);
    }
    return color;
}


std::vector<int> get_custom_vivid_color_from_frequency(float frequency, std::vector<std::vector<int>> colors) {
    // Ensure there are at least three colors defined by the user
    if (colors.size() < 3) return {0, 0, 0};

    // Define colors using user-defined inputs
    static int last_increase_color_index = 2; // Index for positive change
    static int last_decrease_color_index = 0; // Index for negative change
    static int last_neutral_color_index = 1;  // Index for no change
    static float prev_frequency = 220.0f;

    std::vector<int> color;

    if (frequency > prev_frequency) {
        // Positive frequency change
        color = colors[last_increase_color_index];
        last_increase_color_index = (last_increase_color_index + 1) % colors.size();
    } else if (frequency < prev_frequency) {
        // Negative frequency change
        color = colors[last_decrease_color_index];
        last_decrease_color_index = (last_decrease_color_index + 1) % colors.size();
    } else {
        // No frequency change
        color = colors[last_neutral_color_index];
        last_neutral_color_index = (last_neutral_color_index + 1) % colors.size();
    }

    // Update the previous frequency
    prev_frequency = frequency;

    return color;
}

// A map to store the last sent color for each light
std::unordered_map<std::string, std::vector<int>> last_sent_color;
std::unordered_map<std::string, int> last_color_index;  // To track the last color index for each light

// Function to cycle through user-defined colors if the same color is selected
std::vector<int> get_next_color(const std::vector<std::vector<int>>& colors, const std::string& ip) {
    // Get the last color index from the map
    int& color_index = last_color_index[ip];

    // If the color list is empty, return a default color (e.g., black or white)
    if (colors.empty()) {
        return {0, 0, 0};  // Default color
    }

    // Move to the next color in the list
    color_index = (color_index + 1) % colors.size(); // Loop back to the first color when we reach the end
    return colors[color_index];
}



    //UDP COMMAND FUNCTIONS     //UDP COMMAND FUNCTIONS



void send_udp_command(const std::string& ip, const std::vector<int>& color, int brightness, const std::vector<std::vector<int>>& user_colors, bool effects_enabled) {
    static auto last_command_time = std::chrono::steady_clock::now();  // Track the time of the last command sent
    auto now = std::chrono::steady_clock::now();
    auto elapsed_time = std::chrono::duration_cast<std::chrono::milliseconds>(now - last_command_time);

    // Check if enough time has passed since the last command
    if (elapsed_time.count() >= MIN_UPDATE_INTERVAL_MS) {
        if (effects_enabled) {
            // If effects are enabled, cycle through colors or apply smoothing as needed
            if (last_sent_color[ip] == color) {
                std::cout << "Selected color is the same as the previous one, cycling to the next color." << std::endl;

                // Get the next color in the user-defined colors list
                std::vector<int> alternate_color = get_next_color(user_colors, ip);

                // Send the next color instead of the same color
                last_sent_color[ip] = alternate_color; // Update the last sent color
                boost::asio::ip::udp::resolver resolver(global_io_context);
                boost::asio::ip::udp::endpoint receiver_endpoint = *resolver.resolve(boost::asio::ip::udp::v4(), ip, std::to_string(UDP_PORT)).begin();

                json payload;
                payload["method"] = "setPilot";
                payload["params"] = {{"r", alternate_color[0]}, {"g", alternate_color[1]}, {"b", alternate_color[2]}, {"dimming", brightness}};

                std::string message = payload.dump();
                udp_socket.send_to(boost::asio::buffer(message), receiver_endpoint);
                std::cout << "Sent alternate color to " << ip << " with color [" 
                          << alternate_color[0] << ", " << alternate_color[1] << ", " 
                          << alternate_color[2] << "] and brightness " << brightness << std::endl;
            } else {
                // Send the original color
                last_sent_color[ip] = color;
                boost::asio::ip::udp::resolver resolver(global_io_context);
                boost::asio::ip::udp::endpoint receiver_endpoint = *resolver.resolve(boost::asio::ip::udp::v4(), ip, std::to_string(UDP_PORT)).begin();

                json payload;
                payload["method"] = "setPilot";
                payload["params"] = {{"r", color[0]}, {"g", color[1]}, {"b", color[2]}, {"dimming", brightness}};

                std::string message = payload.dump();
                udp_socket.send_to(boost::asio::buffer(message), receiver_endpoint);
                std::cout << "Sent CHANGE_COLOR command to " << ip << " with color [" 
                          << color[0] << ", " << color[1] << ", " << color[2] 
                          << "] and brightness " << brightness << std::endl;
            }
        } else {
            // If no effects are enabled, use the predefined user color directly
            last_sent_color[ip] = color; // Ensure the last sent color is updated
            boost::asio::ip::udp::resolver resolver(global_io_context);
            boost::asio::ip::udp::endpoint receiver_endpoint = *resolver.resolve(boost::asio::ip::udp::v4(), ip, std::to_string(UDP_PORT)).begin();

            json payload;
            payload["method"] = "setPilot";
            payload["params"] = {{"r", color[0]}, {"g", color[1]}, {"b", color[2]}, {"dimming", brightness}};

            std::string message = payload.dump();
            udp_socket.send_to(boost::asio::buffer(message), receiver_endpoint);
            std::cout << "Sent CHANGE_COLOR command to " << ip << " with color [" 
                      << color[0] << ", " << color[1] << ", " << color[2] 
                      << "] and brightness " << brightness << std::endl;
        }

        // Update the last command time after sending the command
        last_command_time = now;
    } else {
        std::cout << "Skipping command to " << ip << " due to minimum update interval." << std::endl;
    }
}

void send_udp_command_off(const std::string& ip) {
    try {
        boost::asio::ip::udp::resolver resolver(global_io_context);
        boost::asio::ip::udp::endpoint receiver_endpoint = *resolver.resolve(boost::asio::ip::udp::v4(), ip, std::to_string(UDP_PORT)).begin();

        json payload;
        payload["method"] = "setPilot";
        payload["params"] = {{"state", false}};

        std::string message = payload.dump();
        udp_socket.send_to(boost::asio::buffer(message), receiver_endpoint);
    } catch (std::exception& e) {
        std::cerr << "send_udp_command_off error: " << e.what() << std::endl;
    }
}



    // FFT FUNCTIONS    // FFT FUNCTIONS



float process_audio(const std::vector<int16_t>& audio_data, std::vector<float>& magnitudes) {
    int N = fft_size; // Use the pre-defined FFT size

    static std::vector<double> fft_input(N); // Input buffer for FFT
    static fftw_complex* fft_output = reinterpret_cast<fftw_complex*>(fftw_malloc(sizeof(fftw_complex) * (N / 2 + 1)));

    // Check if audio_data size is sufficient
    if (audio_data.size() < N * NUM_CHANNELS) {
        std::cerr << "Audio data is smaller than expected size!" << std::endl;
        return 0.0f; // Or handle the error appropriately (e.g., return a default value)
    }

    // Fill the input buffer for FFT
    for (int i = 0; i < N; ++i) {
        fft_input[i] = static_cast<double>(audio_data[i * NUM_CHANNELS]); // Assuming NUM_CHANNELS is 2
    }

    // Execute the FFT using a cached plan
    static fftw_plan plan = nullptr;
    if (!plan) {
        plan = fftw_plan_dft_r2c_1d(N, fft_input.data(), fft_output, FFTW_MEASURE);
    }
    fftw_execute(plan);

    // Compute magnitudes from FFT output
    magnitudes.resize(N / 2 + 1);
    for (int i = 0; i < N / 2 + 1; ++i) {
        magnitudes[i] = std::sqrt(fft_output[i][0] * fft_output[i][0] + fft_output[i][1] * fft_output[i][1]);
    }

    // Find the bin with the maximum magnitude
    int max_index = std::distance(magnitudes.begin(), std::max_element(magnitudes.begin(), magnitudes.end()));
    float max_magnitude = magnitudes[max_index];

    // Convert the bin index to a frequency
    float frequency = static_cast<float>(max_index) * SAMPLE_RATE / N;

    max_frequency.store(max_magnitude); // Update the atomic value

    return frequency; // Return the frequency for further processing
}


void cleanup_fft() {
    // Destroy the FFTW plan
    if (fft_plan) {
        fftw_destroy_plan(fft_plan);
        fft_plan = nullptr;
    }

    // Free allocated FFTW output
    if (fft_output) {
        fftw_free(fft_output);
        fft_output = nullptr;
    }

    // Reset initialization flag
    fft_initialized = false;

    std::cout << "FFT resources cleaned up." << std::endl;
}


void initialize_fft(int N) {
    // Check if FFT is already initialized
    if (fft_initialized) {
        std::cerr << "FFT already initialized. Cleaning up before reinitializing." << std::endl;
        cleanup_fft();
    }

    // Set FFT size
    fft_size = N;
    fft_input.resize(N);

    // Allocate memory for FFTW output
    fft_output = static_cast<fftw_complex*>(fftw_malloc(sizeof(fftw_complex) * (N / 2 + 1)));
    if (!fft_output) {
        std::cerr << "Error: Failed to allocate fft_output." << std::endl;
        exit(EXIT_FAILURE); // Exit if allocation fails
    }

    // Create FFTW plan
    fft_plan = fftw_plan_dft_r2c_1d(N, fft_input.data(), fft_output, FFTW_MEASURE);
    if (!fft_plan) {
        std::cerr << "Error: Failed to create FFTW plan." << std::endl;
        fftw_free(fft_output); // Free previously allocated output
        exit(EXIT_FAILURE);
    }

    std::cout << "FFT initialized with size: " << N << std::endl;

    // Mark as initialized
    fft_initialized = true;
}




    // AUDIO PROCESSING FUNCTIONS   // AUDIO PROCESSING FUNCTIONS



PaSampleFormat get_device_sample_format(int deviceIndex) {
    const PaDeviceInfo* deviceInfo = Pa_GetDeviceInfo(deviceIndex);

    // Default to paInt16 if unsure (commonly supported)
    if (!deviceInfo) return paInt16;

    // Try common sample formats (e.g., paFloat32, paInt16)
    if (deviceInfo->maxInputChannels > 0) {
        // For simplicity, assume Voicemeeter uses paFloat32
        return paFloat32;
    }
    return paInt16; // Fallback
}


// CALLBACK FUNCTION

static int process_audio_data(const void* inputBuffer, void* outputBuffer,
                              unsigned long framesPerBuffer, const PaStreamCallbackTimeInfo* timeInfo,
                              PaStreamCallbackFlags statusFlags, void* userData) {

    // Check if FFT is initialized before proceeding
    if (!fft_initialized) {
        std::cerr << "Waiting for FFT initialization...\n";
        return paContinue;  // Skip processing until FFT is ready
    }

    // Handle null input buffer
    if (inputBuffer == nullptr) {
        std::cerr << "Input buffer is null. PaStreamCallbackFlags: " << statusFlags << std::endl;
        return paContinue;
    }

    // Allocate and initialize audio data buffer
    std::vector<int16_t> audio_data(framesPerBuffer * NUM_CHANNELS);

    // Check if the audio data buffer is large enough
    if (audio_data.size() < framesPerBuffer * NUM_CHANNELS) {
        std::cerr << "Audio data buffer too small!" << std::endl;
        return paAbort;  // Abort if the buffer size is incorrect
    }

    const float* float_data = static_cast<const float*>(inputBuffer);

    // Convert float data to 16-bit integer format and check for silence
    bool is_silent = true;
    for (unsigned long i = 0; i < framesPerBuffer * NUM_CHANNELS; ++i) {
        audio_data[i] = static_cast<int16_t>(float_data[i] * 32767);
        if (audio_data[i] != 0) {
            is_silent = false;
        }
    }

    // Skip processing if all audio data is zero
    if (is_silent) {
        std::cerr << "All captured audio data is zero. Skipping processing." << std::endl;
        return paContinue;
    }

    // Calculate RMS volume to detect low-level audio
    if (enable_silence_threshold) {
        static float observed_min_volume = std::numeric_limits<float>::max();
        static float observed_max_volume = std::numeric_limits<float>::min();

        float volume = 0.0f;
        for (const auto& sample : audio_data) {
            volume += sample * sample;
        }
        volume = std::sqrt(volume / audio_data.size());

        // Update observed volume range dynamically
        observed_min_volume = std::min(observed_min_volume, volume);
        observed_max_volume = std::max(observed_max_volume, volume);

        // Adjust the silence threshold dynamically
        float dynamic_silence_threshold = observed_min_volume + 
                                          (observed_max_volume - observed_min_volume) * 0.1f;

        std::cout << "Dynamic Silence Threshold: " << dynamic_silence_threshold 
                  << ", Current Volume: " << volume << std::endl;

        if (volume < dynamic_silence_threshold) {
            std::cout << "Volume below threshold. Skipping processing." << std::endl;
            return paContinue;
        }
    }

    // Apply dynamic volume leveling
    float total_volume = 0.0f;
    for (const auto& sample : audio_data) {
        total_volume += sample * sample;
    }
    float rms_volume = std::sqrt(total_volume / audio_data.size());
    float target_volume = 10000.0f; // Target RMS volume
    float gain = target_volume / std::max(rms_volume, 1.0f); // Avoid division by zero

    // Apply gain and clamp the values to avoid overflow
    for (auto& sample : audio_data) {
        float scaled_sample = static_cast<float>(sample) * gain;
        if (scaled_sample > 32767.0f) {
            sample = 32767;
        } else if (scaled_sample < -32768.0f) {
            sample = -32768;
        } else {
            sample = static_cast<int16_t>(scaled_sample);
        }
    }

    std::cout << "Applied Gain: " << gain << ", Adjusted RMS Volume: " << rms_volume * gain << std::endl;

    // Process audio to get magnitudes and frequency
    std::vector<float> magnitudes;
    float frequency = process_audio(audio_data, magnitudes);
    std::cout << "Processed Frequency: " << frequency << std::endl;

    // Calculate the average energy from the magnitudes
    float current_energy = std::accumulate(magnitudes.begin(), magnitudes.end(), 0.0f) / magnitudes.size();
    static std::vector<float> recent_energies;
    if (recent_energies.size() > recent_energies_size) {
        recent_energies.erase(recent_energies.begin());
    }
    recent_energies.push_back(current_energy);
    dynamic_threshold = (std::accumulate(recent_energies.begin(), recent_energies.end(), 0.0f) / recent_energies.size()) * sensitivity_multiplier;

    // Frequency update logic
    static float prev_frequency = 0.0f;  // Variable to hold the previous frequency value
    const float frequency_change_threshold = 0.5f; // Minimum frequency change for a new update

    // Check if the frequency has changed enough to trigger an update
    if (fabs(frequency - prev_frequency) >= frequency_change_threshold) {
        // Processing light effects
        try {
            for (const auto& config : *reinterpret_cast<std::vector<LightConfig>*>(userData)) {
                // Get the color based on the current frequency
                std::vector<int> color = get_custom_vivid_color_from_frequency(frequency, config.colors);

                // Clamp the color values
                for (auto& value : color) {
                    value = bounded_value(value, 0, 255); // Use the renamed function
                }
                
                std::cout << "Selected color: [" << color[0] << ", " << color[1] << ", " << color[2] << "] for frequency: " << frequency << std::endl;

                // Apply the effect to the light
                switch (config.effect) {
                    case CHANGE_COLOR:
                        if (enable_beat_detection && current_energy > dynamic_threshold && hysteresis_counter == 0) {
                            send_udp_command(config.ip, color, target_brightness, config.colors, effects_enabled);
                            std::cout << "Sent CHANGE_COLOR command to " << config.ip << " with color " << color[0] << "," << color[1] << "," << color[2] << " and brightness " << target_brightness << std::endl;
                        }
                        break;
                    case ADJUST_BRIGHTNESS:
                        if (current_energy > dynamic_threshold) {
                            current_brightness = std::min(255, static_cast<int>(target_brightness + (current_energy * brightness_multiplier)));
                            send_udp_command(config.ip, color, current_brightness, config.colors, effects_enabled);
                            std::cout << "Sent ADJUST_BRIGHTNESS command to " << config.ip << " with color " << color[0] << "," << color[1] << "," << color[2] << " and brightness " << current_brightness << std::endl;
                        }
                        break;
                    case TURN_OFF_ON:
                        if (enable_beat_detection && current_energy > dynamic_threshold && hysteresis_counter == 0) {
                            send_udp_command_off(config.ip);
                            std::cout << "Sent TURN_OFF_ON command to turn off " << config.ip << std::endl;
                        }
                        break;
                }
            }
        } catch (const std::exception& e) {
            std::cerr << "Exception in callback: " << e.what() << std::endl;
            return paComplete; // Stop the stream if there is an exception
        } catch (...) {
            std::cerr << "Unknown exception in callback" << std::endl;
            return paComplete; // Stop the stream if there is an unknown exception
        }

        // Update the previous frequency to the current frequency
        prev_frequency = frequency;
    }

    // Reduce the hysteresis counter if it's greater than zero
    if (hysteresis_counter > 0) {
        hysteresis_counter--;
    }

    // Periodic updates based on time interval
    static auto last_update_time = std::chrono::steady_clock::now();
    auto now = std::chrono::steady_clock::now();
    auto elapsed_time = std::chrono::duration_cast<std::chrono::milliseconds>(now - last_update_time);

    if (elapsed_time.count() >= MIN_UPDATE_INTERVAL_MS) {
        // Update the light based on the frequency range
        for (const auto& config : *reinterpret_cast<std::vector<LightConfig>*>(userData)) {
            std::vector<int> target_color = map_frequency_to_color(frequency, config.colors, SAMPLE_RATE);
            static std::vector<int> prev_color = {0, 0, 0};
            std::vector<int> color;
            if (apply_smooth_transition) {
                color = smooth_color_transition(prev_color, target_color, 0.1f); // Blend 10% per frame
            } else {
                color = target_color; // Directly use the target color without transition
            }

            prev_color = color;

            // Send the updated color to the light
            send_udp_command(config.ip, color, target_brightness, config.colors, effects_enabled);
            std::cout << "Sent periodic update command to " << config.ip << " with color [" << color[0] << ", " << color[1] << ", " << color[2] << "] and brightness " << current_brightness << std::endl;
        }
        last_update_time = now;
    }

    return paContinue;
}


void audio_processing_loop(const std::vector<LightConfig>& light_configs) {
    PaError err = Pa_Initialize();
    if (err != paNoError) {
        std::cerr << "PortAudio initialization error: " << Pa_GetErrorText(err) << std::endl;
        return;
    }

    int deviceIndex = -1;
    int numDevices = Pa_GetDeviceCount();
    for (int i = 0; i < numDevices; ++i) {
        const PaDeviceInfo* deviceInfo = Pa_GetDeviceInfo(i);
        if (deviceInfo != nullptr && std::string(deviceInfo->name) == audio_device) {
            deviceIndex = i;
            break;
        }
    }

    if (deviceIndex == -1) {
        std::cerr << "Device '" << audio_device << "' not found." << std::endl;
        Pa_Terminate();
        return;
    }

    const PaDeviceInfo* deviceInfo = Pa_GetDeviceInfo(deviceIndex);
    if (deviceInfo == nullptr) {
        std::cerr << "Unable to retrieve device info for device index " << deviceIndex << "." << std::endl;
        Pa_Terminate();
        return;
    }

    std::cout << "Using audio device: " << deviceInfo->name << std::endl;

    PaStreamParameters inputParameters;
    inputParameters.device = deviceIndex;
    inputParameters.channelCount = NUM_CHANNELS = deviceInfo->maxInputChannels; // Use the device's supported channel count
    inputParameters.sampleFormat = paFloat32;  // Ensure this matches your expected format
    inputParameters.suggestedLatency = deviceInfo->defaultLowInputLatency * 2;  // Adjust for a higher buffer
    inputParameters.hostApiSpecificStreamInfo = nullptr;

    PaStream* stream;
    err = Pa_OpenStream(&stream, &inputParameters, nullptr, SAMPLE_RATE, FRAMES_PER_BUFFER, paClipOff, process_audio_data, (void*)&light_configs);
    if (err != paNoError) {
        std::cerr << "PortAudio open stream error: " << Pa_GetErrorText(err) << std::endl;
        Pa_Terminate();
        return;
    }

    err = Pa_StartStream(stream);
    if (err != paNoError) {
        std::cerr << "PortAudio start stream error: " << Pa_GetErrorText(err) << std::endl;
        Pa_CloseStream(stream);
        Pa_Terminate();
        return;
    }

    std::cout << "Processing audio... Press Ctrl+C to stop." << std::endl;

    while (running) {
        PaError streamStatus = Pa_IsStreamActive(stream);
        if (streamStatus == 0) { // Stream inactive
            std::cerr << "Stream stopped unexpectedly! Reinitializing stream..." << std::endl;

            // Close and reopen the stream to reinitialize
            err = Pa_StopStream(stream);
            if (err != paNoError) {
                std::cerr << "PortAudio stop stream error: " << Pa_GetErrorText(err) << " (error code: " << err << ")" << std::endl;
            }

            err = Pa_CloseStream(stream);
            if (err != paNoError) {
                std::cerr << "PortAudio close stream error: " << Pa_GetErrorText(err) << " (error code: " << err << ")" << std::endl;
            }

            err = Pa_OpenStream(&stream, &inputParameters, nullptr, SAMPLE_RATE, FRAMES_PER_BUFFER, paClipOff, process_audio_data, (void*)&light_configs);
            if (err != paNoError) {
                std::cerr << "PortAudio reopen stream error: " << Pa_GetErrorText(err) << std::endl;
                break;
            }

            err = Pa_StartStream(stream);
            if (err != paNoError) {
                std::cerr << "PortAudio restart stream error: " << Pa_GetErrorText(err) << std::endl;
                break;
            }

            std::cerr << "Stream reinitialized successfully." << std::endl;
        } else if (streamStatus < 0) { // Error state
            std::cerr << "Stream error: " << Pa_GetErrorText(streamStatus) << " (error code: " << streamStatus << ")" << std::endl;
            break;
        }
        //std::cout << "Main loop running..." << std::endl;
        std::this_thread::sleep_for(std::chrono::milliseconds(1));
    }

    err = Pa_StopStream(stream);
    if (err != paNoError) {
        std::cerr << "PortAudio stop stream error: " << Pa_GetErrorText(err) << " (error code: " << err << ")" << std::endl;
    }

    err = Pa_CloseStream(stream);
    if (err != paNoError) {
        std::cerr << "PortAudio close stream error: " << Pa_GetErrorText(err) << " (error code: " << err << ")" << std::endl;
    }

    Pa_Terminate();
    std::cout << "Audio processing stopped." << std::endl;
}



    // MAIN FUNCTION    // MAIN FUNCTION



int main(int argc, char* argv[]) {
    // Debugging: Print all arguments
    std::cout << "Received arguments:" << std::endl;
    for (int i = 0; i < argc; ++i) {
        std::cout << "argv[" << i << "] = " << argv[i] << std::endl;
    }

    // Handle calibration flag
    if (argc > 1 && std::string(argv[1]) == "--calibrate") {
        // Default to 5 seconds if no duration is provided
        int duration_seconds = 5;  

        // Check if --duration argument is provided and handle the case where it's in the form --duration=120
        if (argc > 2 && std::string(argv[2]).find("--duration=") != std::string::npos) {
            try {
                // Extract the number after the equals sign
                duration_seconds = std::stoi(std::string(argv[2]).substr(11));  // 11 to skip "--duration="
            } catch (const std::invalid_argument& e) {
                std::cerr << "Invalid duration argument. Using default 5 seconds." << std::endl;
            }
        }

        // Print out the duration being used
        std::cout << "Calibration duration set to: " << duration_seconds << " seconds" << std::endl;

        // Simulate the calibration process with the specified duration
        std::vector<int16_t> dummy_audio(SAMPLE_RATE * duration_seconds, 327); // Simulate audio data for the specified duration
        auto_calibrate_silence_threshold(dummy_audio, SAMPLE_RATE, silence_threshold, duration_seconds);

        return 0;  // Exit after calibration
    }

    // Your other program logic continues here...
    int fft_size = 1024; // Match this to FRAMES_PER_BUFFER
    initialize_fft(fft_size);
    fftw_free(fft_output);

    std::vector<LightConfig> light_configs = load_configuration("config.json", audio_device);

    std::thread audio_thread(audio_processing_loop, std::cref(light_configs));

    std::cout << "Press Enter to stop..." << std::endl;
    std::cin.get();

    running = false;
    audio_thread.join();

    cleanup_fft(); // Clean up FFT resources

    return 0;
}
